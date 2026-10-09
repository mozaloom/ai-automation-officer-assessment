"""Part 1 (Inbox Reviewer) resources, added to the existing Part 2 stack. Reuses its API Gateway, Cognito pool and authorizer.

New resources (all prefixed `xpand-inbox`; remove with `cdk destroy`; see the Part 1 README for cost and cleanup):
- DynamoDB table `InboxState` (on demand): message state, leases, proposals, audit.
- Lambda `inbox-api`: sync, orchestration, policy, approvals, execution (behind API Gateway + Cognito).
- Lambda `inbox-tools`: the READ-ONLY tools, exposed to the model as MCP tools through an AgentCore Gateway Lambda target.
- AgentCore Gateway (IAM inbound) and a second AgentCore Runtime (IAM inbound) running the Strands agent.
- Cognito group `inbox-reviewers`.
Secrets (`xpand/inbox/clickup`, `xpand/inbox/graph`) are created outside CDK by the setup scripts so no secret value is ever in a template.
"""

from __future__ import annotations

import sys
from pathlib import Path

from aws_cdk import CfnOutput, Duration, RemovalPolicy, aws_apigateway as apigw, aws_bedrockagentcore as agentcore, aws_cognito as cognito, aws_dynamodb as ddb, aws_iam as iam, aws_lambda as lambda_, aws_logs as logs, aws_s3_assets as s3_assets
from constructs import Construct

PART1 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PART1 / "src"))
from inbox.tools import TOOL_SCHEMAS  # noqa: E402  (the single source of truth for the tool contracts)

PREFIX = "xpand-inbox"
CLICKUP_SECRET = "xpand/inbox/clickup"
GRAPH_SECRET = "xpand/inbox/graph"
MODEL_ID = "us.amazon.nova-2-lite-v1:0"
FOUNDATION_MODEL_ID = "amazon.nova-2-lite-v1:0"


class InboxAutomation(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, api: apigw.RestApi, authorizer: apigw.IAuthorizer, user_pool: cognito.UserPool, web_origin: str,
                 agent_zip: Path, lambda_zip: Path, outlook_mode: str = "sample", clickup_mode: str = "api") -> None:
        super().__init__(scope, construct_id)
        from aws_cdk import Stack

        stack = Stack.of(self)
        account, region = stack.account, stack.region

        self.table = ddb.Table(
            self, "InboxState", table_name=f"{PREFIX}-state",
            partition_key=ddb.Attribute(name="pk", type=ddb.AttributeType.STRING), sort_key=ddb.Attribute(name="sk", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST, point_in_time_recovery_specification=ddb.PointInTimeRecoverySpecification(point_in_time_recovery_enabled=True),
            removal_policy=RemovalPolicy.DESTROY,  # assessment POC: the table goes with the stack
        )
        for index, pk, sk in (("gsi1", "gsi1pk", "gsi1sk"), ("gsi2", "gsi2pk", "gsi2sk")):
            self.table.add_global_secondary_index(index_name=index, partition_key=ddb.Attribute(name=pk, type=ddb.AttributeType.STRING), sort_key=ddb.Attribute(name=sk, type=ddb.AttributeType.STRING))

        group = cognito.CfnUserPoolGroup(self, "ReviewerGroup", user_pool_id=user_pool.user_pool_id, group_name="inbox-reviewers", description="May sync the inbox and approve, edit or reject proposed actions")

        secret_arn = lambda name: f"arn:aws:secretsmanager:{region}:{account}:secret:{name}-*"

        # ---------------------------------------------------------------- tools Lambda (read-only) behind the Gateway
        tools_fn = lambda_.Function(
            self, "ToolsFn", function_name=f"{PREFIX}-tools", runtime=lambda_.Runtime.PYTHON_3_13, architecture=lambda_.Architecture.ARM_64, handler="inbox.tools.handler",
            code=lambda_.Code.from_asset(str(lambda_zip)), timeout=Duration.seconds(30), memory_size=256,
            environment={"CLICKUP_MODE": clickup_mode, "OUTLOOK_MODE": outlook_mode, "CLICKUP_SECRET_ID": CLICKUP_SECRET, "GRAPH_SECRET_ID": GRAPH_SECRET},
            log_group=logs.LogGroup(self, "ToolsLogs", retention=logs.RetentionDays.ONE_MONTH, removal_policy=RemovalPolicy.DESTROY),
        )
        tools_fn.add_to_role_policy(iam.PolicyStatement(sid="ReadClickUpSecret", actions=["secretsmanager:GetSecretValue"], resources=[secret_arn(CLICKUP_SECRET)]))
        tools_fn.add_to_role_policy(iam.PolicyStatement(sid="GraphSecret", actions=["secretsmanager:GetSecretValue", "secretsmanager:PutSecretValue"], resources=[secret_arn(GRAPH_SECRET)]))  # token rotation

        self.gateway = agentcore.Gateway(self, "Gateway", gateway_name=f"{PREFIX}-tools", description="Read-only ClickUp and Outlook tools for the Inbox Reviewer agent", authorizer_configuration=agentcore.GatewayAuthorizer.using_aws_iam())
        self.gateway.add_lambda_target(
            "ToolsTarget", gateway_target_name="inbox-tools", lambda_function=tools_fn, description="Search and read tasks, read an email, create a reply draft. Cannot create tasks or send mail.",
            tool_schema=agentcore.ToolSchema.from_inline([
                agentcore.ToolDefinition(
                    name=t["name"], description=t["description"],
                    input_schema=agentcore.SchemaDefinition(
                        type=agentcore.SchemaDefinitionType.OBJECT, required=t["inputSchema"].get("required", []),
                        properties={k: agentcore.SchemaDefinition(type=getattr(agentcore.SchemaDefinitionType, v["type"].upper()), description=v.get("description")) for k, v in t["inputSchema"]["properties"].items()},
                    ),
                )
                for t in TOOL_SCHEMAS
            ]),
        )

        # ---------------------------------------------------------------- the agent runtime (IAM inbound; invoked by inbox-api only)
        agent_code = s3_assets.Asset(self, "InboxAgentCode", path=str(agent_zip))
        role = iam.Role(
            self, "RuntimeRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com", conditions={"StringEquals": {"aws:SourceAccount": account}, "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account}:*"}}),
            description="Execution role for the Inbox Reviewer agent (model access and read-only tools only)",
        )
        log_arn = f"arn:aws:logs:{region}:{account}:log-group:/aws/bedrock-agentcore/runtimes/*"
        role.add_to_policy(iam.PolicyStatement(sid="Logs", actions=["logs:CreateLogGroup", "logs:DescribeLogStreams"], resources=[log_arn]))
        role.add_to_policy(iam.PolicyStatement(sid="LogsDescribe", actions=["logs:DescribeLogGroups"], resources=[f"arn:aws:logs:{region}:{account}:log-group:*"]))
        role.add_to_policy(iam.PolicyStatement(sid="LogsWrite", actions=["logs:CreateLogStream", "logs:PutLogEvents"], resources=[f"{log_arn}:log-stream:*"]))
        role.add_to_policy(iam.PolicyStatement(sid="Tracing", actions=["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"], resources=["*"]))
        role.add_to_policy(iam.PolicyStatement(sid="Metrics", actions=["cloudwatch:PutMetricData"], resources=["*"], conditions={"StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}}))
        role.add_to_policy(iam.PolicyStatement(
            sid="BedrockNova2Lite", actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            resources=[f"arn:aws:bedrock:{region}:{account}:inference-profile/{MODEL_ID}", f"arn:aws:bedrock:*::foundation-model/{FOUNDATION_MODEL_ID}"]))
        agent_code.grant_read(role)
        self.gateway.grant_invoke(role)  # the only door to ClickUp/Outlook, and it only has read tools

        self.runtime = agentcore.CfnRuntime(
            self, "Runtime", agent_runtime_name="inbox_reviewer_agent", description="Strands Inbox Reviewer: proposes an action for one email",
            role_arn=role.role_arn,
            agent_runtime_artifact=agentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                code_configuration=agentcore.CfnRuntime.CodeConfigurationProperty(
                    code=agentcore.CfnRuntime.CodeProperty(s3=agentcore.CfnRuntime.S3LocationProperty(bucket=agent_code.s3_bucket_name, prefix=agent_code.s3_object_key)),
                    runtime="PYTHON_3_13", entry_point=["opentelemetry-instrument", "inbox_main.py"])),
            network_configuration=agentcore.CfnRuntime.NetworkConfigurationProperty(network_mode="PUBLIC"),
            protocol_configuration="HTTP",  # no authorizer_configuration: IAM (SigV4) inbound, so only principals with InvokeAgentRuntime can call it
            lifecycle_configuration=agentcore.CfnRuntime.LifecycleConfigurationProperty(idle_runtime_session_timeout=300, max_lifetime=1800),
            environment_variables={
                "BEDROCK_MODEL_ID": MODEL_ID, "AWS_REGION": region, "INBOX_GATEWAY_URL": self.gateway.gateway_url, "LOG_LEVEL": "INFO",
                "AGENT_OBSERVABILITY_ENABLED": "true", "OTEL_PYTHON_DISTRO": "aws_distro", "OTEL_PYTHON_CONFIGURATOR": "aws_configurator",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf", "OTEL_RESOURCE_ATTRIBUTES": "service.name=inbox-reviewer-agent",
            },
        )
        self.runtime.node.add_dependency(role)

        # ---------------------------------------------------------------- inbox-api Lambda
        fn_name = f"{PREFIX}-api"
        api_fn = lambda_.Function(
            self, "ApiFn", function_name=fn_name, runtime=lambda_.Runtime.PYTHON_3_13, architecture=lambda_.Architecture.ARM_64, handler="inbox.api.handler",
            code=lambda_.Code.from_asset(str(lambda_zip)), timeout=Duration.minutes(10), memory_size=512,  # long enough for the asynchronous sync worker
            environment={
                "INBOX_TABLE": self.table.table_name, "OUTLOOK_MODE": outlook_mode, "CLICKUP_MODE": clickup_mode, "CLICKUP_SECRET_ID": CLICKUP_SECRET, "GRAPH_SECRET_ID": GRAPH_SECRET,
                "INBOX_AGENT_RUNTIME_ARN": self.runtime.attr_agent_runtime_arn, "ALLOWED_ORIGIN": web_origin, "INBOX_MAILBOX": "xpand@medgan.ai",
                "INBOX_AUTO_SEND_REPLIES": "false", "INBOX_DEFAULT_PRIORITY": "normal", "INBOX_DEFAULT_STATUS": "to do",
            },
            log_group=logs.LogGroup(self, "ApiLogs", retention=logs.RetentionDays.ONE_MONTH, removal_policy=RemovalPolicy.DESTROY),
        )
        self.table.grant_read_write_data(api_fn)  # includes the indexes
        api_fn.add_to_role_policy(iam.PolicyStatement(sid="ClickUpSecret", actions=["secretsmanager:GetSecretValue"], resources=[secret_arn(CLICKUP_SECRET)]))
        api_fn.add_to_role_policy(iam.PolicyStatement(sid="GraphSecret", actions=["secretsmanager:GetSecretValue", "secretsmanager:PutSecretValue"], resources=[secret_arn(GRAPH_SECRET)]))
        api_fn.add_to_role_policy(iam.PolicyStatement(sid="CallAgent", actions=["bedrock-agentcore:InvokeAgentRuntime"], resources=[self.runtime.attr_agent_runtime_arn, f"{self.runtime.attr_agent_runtime_arn}/runtime-endpoint/*"]))
        api_fn.add_to_role_policy(iam.PolicyStatement(sid="SyncWorker", actions=["lambda:InvokeFunction"], resources=[f"arn:aws:lambda:{region}:{account}:function:{fn_name}"]))  # by name: avoids a circular reference

        # ---------------------------------------------------------------- API Gateway routes (same API, same Cognito authorizer)
        integration = apigw.LambdaIntegration(api_fn, proxy=True)
        inbox = api.root.add_resource("inbox")

        def add(parent: apigw.IResource, name: str, *methods: str) -> apigw.Resource:
            resource = parent.add_resource(name)
            for method in methods:
                resource.add_method(method, integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
            return resource

        add(inbox, "config", "GET")
        messages = add(inbox, "messages", "GET")
        message = add(messages, "{id}", "GET")
        add(message, "retry", "POST")
        add(inbox, "sync", "POST")
        review = add(inbox, "review", "GET")
        review_item = review.add_resource("{id}")
        for action in ("approve", "reject", "edit"):
            add(review_item, action, "POST")
        add(inbox, "activity", "GET")

        CfnOutput(self, "InboxTableName", value=self.table.table_name)
        CfnOutput(self, "InboxGatewayUrl", value=self.gateway.gateway_url)
        CfnOutput(self, "InboxRuntimeArn", value=self.runtime.attr_agent_runtime_arn)
        CfnOutput(self, "InboxApiFunction", value=api_fn.function_name)
