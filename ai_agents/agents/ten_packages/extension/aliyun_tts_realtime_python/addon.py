#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
#
from ten_runtime import Addon, register_addon_as_extension, TenEnv


@register_addon_as_extension("aliyun_tts_realtime_python")
class AliyunTTSRealtimeExtensionAddon(Addon):
    def on_create_instance(self, ten_env: TenEnv, name: str, context) -> None:
        from .extension import AliyunTTSRealtimeExtension

        ten_env.log_info("AliyunTTSRealtimeExtensionAddon on_create_instance")
        ten_env.on_create_instance_done(AliyunTTSRealtimeExtension(name), context)
