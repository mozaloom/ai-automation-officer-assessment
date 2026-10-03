"""One stack: Cognito -> API Gateway -> AgentCore Runtime -> S3 (POS data), plus Amplify hosting.

Everything is prefixed `pos-availability` so it never collides with other apps in the shared account.
"""

from __future__ import annotations

import json
from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    Fn,
    RemovalPolicy,
    Stack,
    aws_amplify as amplify,
    aws_apigateway as apigw,
    aws_bedrockagentcore as agentcore,
    aws_cognito as cognito,
    aws_iam as iam,
    aws_logs as logs,
    aws_s3 as s3,
    aws_s3_assets as s3_assets,
)
from constructs import Construct

ROOT = Path(__file__).resolve().parents[2]
MODEL_ID = "us.amazon.nova-2-lite-v1:0"
FOUNDATION_MODEL_ID = "amazon.nova-2-lite-v1:0"
RUNTIME_NAME = "pos_availability_agent"
DASHBOARD_SESSION = "pos-availability-dashboard-shared-session"  # >= 33 chars; one warm microVM serves the stateless dashboard
JSON = "application/json"
API_ERROR = '{"error":{"code":"%s","message":"%s"}}'


class AvailabilityStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, custom_domain: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.custom_domain = custom_domain
        web_origin = f"https://{custom_domain}"

        data_bucket = self._data_bucket()
        user_pool, client = self._cognito()
        runtime = self._runtime(data_bucket, user_pool, client, web_origin)
        api = self._api(runtime, user_pool, web_origin)

        web = self._web(web_origin)

        CfnOutput(self, "ApiUrl", value=api.url)
        CfnOutput(self, "AmplifyAppId", value=web.attr_app_id)
        CfnOutput(self, "AmplifyDefaultDomain", value=web.attr_default_domain)
        CfnOutput(self, "WebUrl", value=web_origin)
        CfnOutput(self, "RuntimeArn", value=runtime.attr_agent_runtime_arn)
        CfnOutput(self, "DataBucketName", value=data_bucket.bucket_name)
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=client.user_pool_client_id)

    # ------------------------------------------------------------------ web hosting (Amplify, static export, manual deploys)

    def _web(self, web_origin: str) -> amplify.CfnApp:
        headers = f"""customHeaders:
  - pattern: '**'
    headers:
      - key: Strict-Transport-Security
        value: max-age=31536000; includeSubDomains
      - key: X-Content-Type-Options
        value: nosniff
      - key: X-Frame-Options
        value: DENY
      - key: Referrer-Policy
        value: strict-origin-when-cross-origin
      - key: Permissions-Policy
        value: camera=(), microphone=(), geolocation=()
      - key: Content-Security-Policy
        value: "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self' https://*.execute-api.{self.region}.amazonaws.com https://cognito-idp.{self.region}.amazonaws.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
"""
        app = amplify.CfnApp(self, "WebApp", name="pos-availability-web", platform="WEB", description="XPAND Availability (Next.js static export)", custom_headers=headers)
        branch = amplify.CfnBranch(self, "WebBranch", app_id=app.attr_app_id, branch_name="main", stage="PRODUCTION", enable_auto_build=False)
        # Same pattern the account's other apps use: the full sub-domain is the domain name; Amplify manages the
        # certificate and creates only its own records in the existing Route 53 hosted zone.
        domain = amplify.CfnDomain(self, "WebDomain", app_id=app.attr_app_id, domain_name=self.custom_domain,
                                   sub_domain_settings=[amplify.CfnDomain.SubDomainSettingProperty(branch_name=branch.branch_name, prefix="")])
        domain.node.add_dependency(branch)
        return app

    # ------------------------------------------------------------------ data

    def _data_bucket(self) -> s3.Bucket:
        return s3.Bucket(
            self, "DataBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,  # scripts/destroy.sh empties it first
        )

    # ------------------------------------------------------------------ AgentCore runtime

    def _runtime(self, data_bucket: s3.Bucket, user_pool: cognito.UserPool, client: cognito.UserPoolClient, web_origin: str) -> agentcore.CfnRuntime:
        code = s3_assets.Asset(self, "AgentCode", path=str(ROOT / "build" / "agent.zip"))
        self.code_version = code.asset_hash[:8]  # new code => new dashboard session id => a fresh microVM (a warm one would keep serving old code)
        role = iam.Role(
            self, "RuntimeRole",
            assumed_by=iam.ServicePrincipal(
                "bedrock-agentcore.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:*"},
                },
            ),
            description="Execution role for the POS availability agent (least privilege)",
        )
        log_arn = f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock-agentcore/runtimes/*"
        role.add_to_policy(iam.PolicyStatement(sid="Logs", actions=["logs:CreateLogGroup", "logs:DescribeLogStreams"], resources=[log_arn]))
        role.add_to_policy(iam.PolicyStatement(sid="LogsDescribe", actions=["logs:DescribeLogGroups"], resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:*"]))
        role.add_to_policy(iam.PolicyStatement(sid="LogsWrite", actions=["logs:CreateLogStream", "logs:PutLogEvents"], resources=[f"{log_arn}:log-stream:*"]))
        role.add_to_policy(iam.PolicyStatement(
            sid="Tracing", actions=["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"], resources=["*"]))
        role.add_to_policy(iam.PolicyStatement(
            sid="Metrics", actions=["cloudwatch:PutMetricData"], resources=["*"], conditions={"StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}}))
        role.add_to_policy(iam.PolicyStatement(
            sid="BedrockNova2Lite",
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            resources=[
                f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/{MODEL_ID}",
                f"arn:aws:bedrock:*::foundation-model/{FOUNDATION_MODEL_ID}",
            ],
        ))
        data_bucket.grant_read(role, "pos_availability.csv")
        code.grant_read(role)

        runtime = agentcore.CfnRuntime(
            self, "Runtime",
            agent_runtime_name=RUNTIME_NAME,
            description="Strands Availability Agent + POS dashboard analytics",
            role_arn=role.role_arn,
            agent_runtime_artifact=agentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                code_configuration=agentcore.CfnRuntime.CodeConfigurationProperty(
                    code=agentcore.CfnRuntime.CodeProperty(s3=agentcore.CfnRuntime.S3LocationProperty(bucket=code.s3_bucket_name, prefix=code.s3_object_key)),
                    runtime="PYTHON_3_13",
                    entry_point=["opentelemetry-instrument", "main.py"],
                )
            ),
            network_configuration=agentcore.CfnRuntime.NetworkConfigurationProperty(network_mode="PUBLIC"),
            protocol_configuration="HTTP",
            # AgentCore validates the caller's Cognito ID token itself (defence in depth behind the API Gateway authorizer).
            authorizer_configuration=agentcore.CfnRuntime.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=agentcore.CfnRuntime.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool.user_pool_id}/.well-known/openid-configuration",
                    allowed_audience=[client.user_pool_client_id],
                )
            ),
            lifecycle_configuration=agentcore.CfnRuntime.LifecycleConfigurationProperty(idle_runtime_session_timeout=600, max_lifetime=3600),
            environment_variables={
                "BEDROCK_MODEL_ID": MODEL_ID,
                "DATA_S3_BUCKET": data_bucket.bucket_name,
                "DATA_S3_KEY": "pos_availability.csv",
                "AWS_REGION": self.region,
                "LOG_LEVEL": "INFO",
                "ALLOWED_ORIGINS": web_origin,  # CORS for streamed responses (API Gateway cannot add headers to them)
                # AgentCore Observability (ADOT): traces, metrics and logs to CloudWatch
                "AGENT_OBSERVABILITY_ENABLED": "true",
                "OTEL_PYTHON_DISTRO": "aws_distro",
                "OTEL_PYTHON_CONFIGURATOR": "aws_configurator",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                "OTEL_RESOURCE_ATTRIBUTES": "service.name=pos-availability-agent",
            },
        )
        runtime.node.add_dependency(role)  # the role's policies must exist before the runtime starts (it creates its log group)
        return runtime

    # ------------------------------------------------------------------ Cognito

    def _cognito(self) -> tuple[cognito.UserPool, cognito.UserPoolClient]:
        pool = cognito.UserPool(
            self, "UserPool",
            user_pool_name="pos-availability-users",
            self_sign_up_enabled=False,  # internal app: users are created by an admin
            sign_in_aliases=cognito.SignInAliases(email=True),
            standard_attributes=cognito.StandardAttributes(email=cognito.StandardAttribute(required=True, mutable=False)),
            password_policy=cognito.PasswordPolicy(min_length=12, require_lowercase=True, require_uppercase=True, require_digits=True, require_symbols=True),
            account_recovery=cognito.AccountRecovery.NONE,
            removal_policy=RemovalPolicy.DESTROY,
        )
        client = pool.add_client(
            "WebClient",
            user_pool_client_name="pos-availability-web",
            generate_secret=False,  # browser client: no secret
            auth_flows=cognito.AuthFlow(user_srp=True, admin_user_password=True),  # SRP for the app; admin flow only for IAM-gated test automation
            prevent_user_existence_errors=True,
            enable_token_revocation=True,
            id_token_validity=Duration.hours(1),
            access_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(7),
        )
        return pool, client

    # ------------------------------------------------------------------ API Gateway -> AgentCore Runtime

    def _api(self, runtime: agentcore.CfnRuntime, user_pool: cognito.UserPool, web_origin: str) -> apigw.RestApi:
        dashboard_session = f"{DASHBOARD_SESSION}-{self.code_version}"

        cors_headers = {"method.response.header.Access-Control-Allow-Origin": f"'{web_origin}'", "method.response.header.Vary": "'Origin'"}
        method_cors = {"method.response.header.Access-Control-Allow-Origin": False, "method.response.header.Vary": False}

        runtime_url = Fn.join("", ["https://bedrock-agentcore.", self.region, ".amazonaws.com/runtimes/", runtime.attr_agent_runtime_id, "/invocations"])
        runtime_address = {  # runtime addressed by id + accountId: no ARN encoding
            "integration.request.querystring.qualifier": "'DEFAULT'",
            "integration.request.querystring.accountId": f"'{self.account}'",
        }
        session_param = "integration.request.header.X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"

        def stream_integration() -> apigw.HttpIntegration:
            """Pass-through (HTTP_PROXY) integration that streams the runtime's Server-Sent Events to the browser.

            The client sends `Authorization: Bearer <Cognito ID token>`; the Cognito authorizer checks it here and the
            runtime's own JWT authorizer checks it again. Response headers (CORS) come from the runtime.
            """
            return apigw.HttpIntegration(
                runtime_url,
                http_method="POST",
                proxy=True,
                options=apigw.IntegrationOptions(
                    response_transfer_mode=apigw.ResponseTransferMode.STREAM,
                    timeout=Duration.seconds(120),
                    request_parameters={session_param: "method.request.header.x-session-id", **runtime_address},
                ),
            )

        def integration(template: str, session_header: str) -> apigw.HttpIntegration:
            return apigw.HttpIntegration(
                runtime_url,
                http_method="POST",
                proxy=False,
                options=apigw.IntegrationOptions(
                    passthrough_behavior=apigw.PassthroughBehavior.NEVER,
                    timeout=Duration.seconds(29),
                    request_parameters={
                        "integration.request.header.Content-Type": f"'{JSON}'",
                        "integration.request.header.Accept": f"'{JSON}'",
                        "integration.request.header.Authorization": "method.request.header.Authorization",  # `Bearer <ID token>` as sent by the client
                        session_param: session_header,
                        **runtime_address,
                    },
                    request_templates={JSON: template},
                    integration_responses=[
                        apigw.IntegrationResponse(status_code="200", response_parameters=cors_headers),
                        apigw.IntegrationResponse(status_code="429", selection_pattern="429", response_parameters=cors_headers,
                                                  response_templates={JSON: API_ERROR % ("busy", "Too many requests. Please wait a moment and try again.")}),
                        apigw.IntegrationResponse(status_code="400", selection_pattern="(400|401|403|404|408|409|424)", response_parameters=cors_headers,
                                                  response_templates={JSON: API_ERROR % ("rejected", "The request could not be processed.")}),
                        apigw.IntegrationResponse(status_code="502", selection_pattern="5\\d\\d", response_parameters=cors_headers,
                                                  response_templates={JSON: API_ERROR % ("upstream_error", "The service is temporarily unavailable. Please try again.")}),
                    ],
                ),
            )

        api = apigw.RestApi(
            self, "Api",
            rest_api_name="pos-availability-api",
            description="Cognito-protected API in front of the AgentCore availability runtime",
            endpoint_types=[apigw.EndpointType.REGIONAL],
            cloud_watch_role=False,  # never touch the shared account-level API Gateway logging role
            deploy_options=apigw.StageOptions(stage_name="v1", throttling_rate_limit=10, throttling_burst_limit=20, metrics_enabled=True),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=[web_origin],
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["Authorization", "Content-Type", "x-session-id"],
                max_age=Duration.hours(1),
            ),
        )
        authorizer = apigw.CognitoUserPoolsAuthorizer(self, "Authorizer", cognito_user_pools=[user_pool], authorizer_name="pos-availability-cognito", identity_source="method.request.header.Authorization")
        validator = apigw.RequestValidator(self, "Validator", rest_api=api, request_validator_name="validate-body-and-params", validate_request_body=True, validate_request_parameters=True)
        ask_model = api.add_model("AskModel", content_type=JSON, model_name="AskRequest", schema=apigw.JsonSchema(
            schema=apigw.JsonSchemaVersion.DRAFT4, type=apigw.JsonSchemaType.OBJECT, required=["prompt"], additional_properties=False,
            properties={
                "prompt": apigw.JsonSchema(type=apigw.JsonSchemaType.STRING, min_length=1, max_length=500),
                "locale": apigw.JsonSchema(type=apigw.JsonSchemaType.STRING, enum=["en", "ar"]),
            },
        ))
        responses = [
            apigw.MethodResponse(status_code=code, response_parameters=method_cors, response_models={JSON: apigw.Model.EMPTY_MODEL}) for code in ("200", "400", "429", "502")
        ]

        api.root.add_resource("ask").add_method(
            "POST",
            stream_integration(),
            authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO,
            request_validator=validator, request_models={JSON: ask_model},
            request_parameters={"method.request.header.x-session-id": True},
        )
        dash_template = (
            '{"action":"dashboard","filters":{"city":"$util.escapeJavaScript($input.params(\'city\'))",'
            '"category":"$util.escapeJavaScript($input.params(\'category\'))","status":"$util.escapeJavaScript($input.params(\'status\'))"}}'
        )
        api.root.add_resource("dashboard").add_method(
            "GET",
            integration(dash_template, f"'{dashboard_session}'"),
            authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO,
            request_validator=validator,
            request_parameters={
                "method.request.header.Authorization": True,
                "method.request.querystring.city": False, "method.request.querystring.category": False, "method.request.querystring.status": False,
            },
            method_responses=responses,
        )

        records_template = (
            '{"action":"records","filters":{"city":"$util.escapeJavaScript($input.params(\'city\'))","category":"$util.escapeJavaScript($input.params(\'category\'))",'
            '"status":"$util.escapeJavaScript($input.params(\'status\'))","product":"$util.escapeJavaScript($input.params(\'product\'))","store":"$util.escapeJavaScript($input.params(\'store\'))"}}'
        )
        api.root.add_resource("records").add_method(
            "GET",
            integration(records_template, f"'{dashboard_session}'"),
            authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO,
            request_validator=validator,
            request_parameters={
                "method.request.header.Authorization": True,
                **{f"method.request.querystring.{k}": False for k in ("city", "category", "status", "product", "store")},
            },
            method_responses=responses,
        )

        # Errors produced by API Gateway itself (401 bad token, 400 validation, 429 throttling) also need CORS headers
        # or the browser cannot read them.
        gateway_headers = {"Access-Control-Allow-Origin": f"'{web_origin}'", "Vary": "'Origin'"}
        for gw_id, gw_type in (("Default4xx", apigw.ResponseType.DEFAULT_4_XX), ("Default5xx", apigw.ResponseType.DEFAULT_5_XX)):
            api.add_gateway_response(gw_id, type=gw_type, response_headers=gateway_headers)
        return api
