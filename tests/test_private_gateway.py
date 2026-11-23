import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import gateway
import providers


class PrivateGatewayTests(unittest.TestCase):
    def setUp(self):
        gateway.disable()
        self.addCleanup(gateway.disable)
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.profile=Path(self.temp.name)/"old-profile.json"
        self.profile.write_text(json.dumps({
            "base":"https://gateway.invalid/v1",
            "source":str(Path(self.temp.name)/"fixture.md"),
            "models":{"planner":"fixture-plan","art_openai":"fixture-image"}
        }),encoding="utf-8")
        local=patch.object(gateway,"PROFILE",self.profile)
        local.start()
        self.addCleanup(local.stop)

    def test_legacy_profile_and_route_are_ignored_until_confirmed(self):
        with patch.dict(os.environ,{"STUDIO_PLANNER":"viru/legacy","STUDIO_ART_OPENAI":"viru/legacy-image"}),patch.object(
            Path,"read_text",side_effect=AssertionError("未授权不得打开已保存网关配置")),patch(
            "gateway.read_vault",side_effect=AssertionError("未授权不得打开凭证文件")):
            self.assertEqual(gateway.profile(),{})
            self.assertEqual(providers.role("planner"),providers.DEFAULTS["planner"])
            self.assertEqual(providers.role("art_openai"),providers.DEFAULTS["art_openai"])
            report=app.model_status()
            self.assertFalse(report["private_gateway_enabled"])
            with self.assertRaisesRegex(ValueError,"确认"):
                app.toggle_private_gateway({"enabled":True})
            with self.assertRaisesRegex(ValueError,"确认"):
                app.configure({"roles":{"planner":"viru/fixture"}})
            with self.assertRaisesRegex(ValueError,"默认关闭"):
                providers.post("viru","chat/completions",{})

    def test_user_confirmation_enables_only_in_current_process(self):
        with patch.dict(os.environ,{"STUDIO_PLANNER":""}),patch("gateway._request",return_value={"data":[]}) as send:
            os.environ.pop("STUDIO_PLANNER",None)
            self.assertTrue(app.toggle_private_gateway({"enabled":True,"confirmation":gateway.CONFIRMATION})["private_gateway_enabled"])
            self.assertEqual(providers.role("planner"),("viru","fixture-plan"))
            with patch.object(Path,"read_text",side_effect=AssertionError("已读配置在进程内使用")):
                self.assertEqual(providers.post("viru","chat/completions",{}),{"data":[]})
                send.assert_called_once()
                self.assertFalse(app.toggle_private_gateway({"enabled":False})["private_gateway_enabled"])
                self.assertEqual(providers.role("planner"),providers.DEFAULTS["planner"])
                with self.assertRaises(ValueError):
                    providers.post("viru","chat/completions",{})
                self.assertEqual(send.call_count,1)
        self.assertTrue(self.profile.is_file())

    def test_configure_probe_also_requires_confirmation(self):
        with patch("gateway.read_vault",side_effect=AssertionError("未经确认不得读取凭证")):
            with self.assertRaisesRegex(ValueError,"确认"):
                gateway.configure("fixture.md",install=True)
        self.assertFalse(gateway.enabled())

