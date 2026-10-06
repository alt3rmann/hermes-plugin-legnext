"""OpenAI-style definitions. Prices are indicative only, not eligibility checks."""

MJ_IMAGINE = {
    'name': 'mj_imagine',
    'description': 'Submit one paid Midjourney image task to Legnext. Check mj_balance first. Flags such as --ar, --v, --niji, --hd, --q, --sref, --cref and --no belong in the prompt. Fast standard generation costs about 80 credits, Turbo 160 ($1 = 1000 credits); actual price varies. wait=false returns a job_id to resume via mj_job, not an image.',
    'parameters': {'type': 'object', 'properties': {
        'prompt': {'type': 'string', 'description': 'Midjourney prompt (1–8192 characters), including any native flags.'},
        'aspect_ratio': {'type': 'string', 'description': 'Append --ar, e.g. 16:9, unless prompt already contains --ar.'},
        'version': {'type': 'string', 'description': 'Append --v, e.g. 8.2; niji 6 appends --niji 6. Ignored when the prompt already specifies a version.'},
        'wait': {'type': 'boolean', 'default': True, 'description': 'Wait for completion and download results (default true).'},
        'timeout': {'type': 'integer', 'description': 'Bounded wait in seconds; timeout does not cancel the server task.'},
    }, 'required': ['prompt']},
}
MJ_JOB = {
    'name': 'mj_job',
    'description': 'Fetch an existing Legnext job by its private job_id (no API key needed). Optionally wait for completion; completed delivery URLs expire, so download promptly. Never resubmit on a polling timeout.',
    'parameters': {'type': 'object', 'properties': {
        'job_id': {'type': 'string', 'description': 'Job UUID returned by mj_imagine or mj_action; treat it as a capability token.'},
        'wait': {'type': 'boolean', 'default': False},
        'timeout': {'type': 'integer', 'description': 'Bounded wait in seconds.'},
        'download': {'type': 'boolean', 'default': True, 'description': 'Save completed media locally immediately (default true).'},
    }, 'required': ['job_id']},
}
MJ_ACTION = {
    'name': 'mj_action',
    'description': 'Create one paid upscale, variation, or reroll from a parent job. Check mj_balance first; variation and standard upscale cost about 120 fast credits, creative upscale 160; actual price varies. For upscale/variation specify image_no from the grid; reroll needs none. Read available_actions on the parent task to see which indexes are allowed.',
    'parameters': {'type': 'object', 'properties': {
        'action': {'type': 'string', 'enum': ['upscale', 'variation', 'reroll']},
        'job_id': {'type': 'string', 'description': 'Parent task UUID.'},
        'image_no': {'type': 'integer', 'description': 'Zero-based index of the image in the parent grid: 0-3 for a normal four-image grid (0-23 for a --draft batch). Required for upscale/variation, ignored for reroll.'},
        'mode': {'type': 'integer', 'enum': [0, 1], 'default': 0, 'description': 'Intensity, defaults to 0. For upscale: 0=subtle, 1=creative. For variation: 0=subtle, 1=strong.'},
        'remix_prompt': {'type': 'string', 'description': 'Optional variation-only remix prompt.'},
        'wait': {'type': 'boolean', 'default': True},
        'timeout': {'type': 'integer', 'description': 'Bounded wait in seconds.'},
    }, 'required': ['action', 'job_id']},
}
MJ_BALANCE = {
    'name': 'mj_balance',
    'description': 'Read the Legnext account balance for free. Call before paid generation/action and after HTTP 402. $1 = 1000 credits; generation about 80 fast/160 Turbo, variation 120 fast, standard upscale 120 fast, creative upscale 160; describe/shorten 20, image-to-video 480p 480 or 720p 1536. Prices are estimates and vary by model and parameters.',
    'parameters': {'type': 'object', 'properties': {}},
}
