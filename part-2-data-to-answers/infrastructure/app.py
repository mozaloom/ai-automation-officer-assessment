#!/usr/bin/env python3
import os

import aws_cdk as cdk

from stacks.availability_stack import AvailabilityStack

app = cdk.App()
AvailabilityStack(
    app,
    "PosAvailabilityStack",
    env=cdk.Environment(account=os.environ["CDK_DEFAULT_ACCOUNT"], region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1")),
    custom_domain=app.node.try_get_context("custom_domain") or "xpand.medgan.ai",
)
cdk.Tags.of(app).add("project", "xpand-assessment-part2")
cdk.Tags.of(app).add("app", "pos-availability")
app.synth()
