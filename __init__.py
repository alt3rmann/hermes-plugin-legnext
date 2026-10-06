"""Legnext tools for Hermes."""

from . import schemas, tools


def register(ctx):
    tools.configure(ctx.get_config)
    ctx.register_tool(name='mj_imagine', toolset='legnext', schema=schemas.MJ_IMAGINE, handler=tools.mj_imagine, emoji='🎨')
    ctx.register_tool(name='mj_job', toolset='legnext', schema=schemas.MJ_JOB, handler=tools.mj_job, emoji='🔎')
    ctx.register_tool(name='mj_action', toolset='legnext', schema=schemas.MJ_ACTION, handler=tools.mj_action, emoji='🖼️')
    ctx.register_tool(name='mj_balance', toolset='legnext', schema=schemas.MJ_BALANCE, handler=tools.mj_balance, emoji='💳')
