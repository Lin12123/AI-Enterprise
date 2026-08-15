import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import app.providers.local_provider as local_provider
from app.providers.router import current_provider_name, parse_featureplan_with_provider
from app.openai_config import safe_exception_message
from cad_dsl.featureplan import FeaturePlan
from policy.policy_engine import PolicyEngine
from solidworks_api.executor import SolidWorksApiExecutor


DANGEROUS_FIELDS = (
    "output_dir",
    "path",
    "file_path",
    "save_path",
    "script",
    "macro",
    "command",
    "python_code",
    "vba_code",
    "powershell",
    "shell",
    "subprocess",
    "delete",
    "remove",
    "overwrite",
)


def featureplan_json(extra_params=None) -> str:
    params = {"length": 120, "width": 80, "thickness": 12, "plane": "Top"}
    if extra_params:
        params.update(extra_params)
    return (
        '{"version":"2.0","unit":"mm","document_type":"part","part_name":"local_part",'
        '"operations":[{"id":"base_001","op":"create_base_plate","params":'
        + repr(params).replace("'", '"').replace("True", "true")
        + '}],"outputs":{"save_sldprt":false,"export_step":false,"capture_png":false}}'
    )


def featureplan_missing_base_solid_json() -> str:
    return (
        '{"version":"2.0","unit":"mm","document_type":"part","part_name":"bad_plan",'
        '"operations":['
        '{"id":"1","op":"create_new_part","params":{}},'
        '{"id":"2","op":"create_sketch","params":{"name":"BaseSketch","plane":"top_face"}},'
        '{"id":"3","op":"sketch_center_rectangle","params":{"sketch":"BaseSketch","center":[0,0],"length":120,"width":80}},'
        '{"id":"4","op":"cut_center_hole","params":{"diameter":6,"target":"base"}}'
        '],"outputs":{}}'
    )


def featureplan_repaired_offcenter_hole_json() -> str:
    return (
        '{"version":"2.0","unit":"mm","document_type":"part","part_name":"repaired_plan",'
        '"metadata":{"name":"repaired_plan","source":"local","inferred_parameters":["5.params.center"],"explicit_parameters":["3.params.length","3.params.width","4.params.depth","5.params.diameter","6.params.count","6.params.spacing"]},'
        '"operations":['
        '{"id":"1","op":"create_new_part","params":{}},'
        '{"id":"2","op":"create_sketch","params":{"name":"BaseSketch","plane":"top_face"}},'
        '{"id":"3","op":"sketch_center_rectangle","params":{"sketch":"BaseSketch","center":[0,0],"length":120,"width":80}},'
        '{"id":"4","op":"extrude_boss","params":{"sketch":"BaseSketch","depth":12}},'
        '{"id":"5","op":"create_through_hole","params":{"plane":"top_face","center":[-40,0],"diameter":6}},'
        '{"id":"6","op":"create_linear_pattern","params":{"seed_feature":"Hole1","direction":"X","count":4,"spacing":20}}'
        '],"outputs":{}}'
    )


def featureplan_invalid_plane_offcenter_hole_json() -> str:
    return (
        '{"version":"2.0","unit":"mm","document_type":"part","part_name":"bad_plane_plan",'
        '"metadata":{"name":"bad_plane_plan","source":"local","inferred_parameters":["5.params.center"],"explicit_parameters":["3.params.length","3.params.width","4.params.depth","5.params.diameter","6.params.count","6.params.spacing"]},'
        '"operations":['
        '{"id":"1","op":"create_new_part","params":{}},'
        '{"id":"2","op":"create_sketch","params":{"name":"BaseSketch","plane":"Top Plane"}},'
        '{"id":"3","op":"sketch_center_rectangle","params":{"sketch":"BaseSketch","center":[0,0],"length":120,"width":80}},'
        '{"id":"4","op":"extrude_boss","params":{"sketch":"BaseSketch","depth":12}},'
        '{"id":"5","op":"create_through_hole","params":{"plane":"upper_face","center":[-40,0],"diameter":6}},'
        '{"id":"6","op":"create_linear_pattern","params":{"seed_feature":"Hole1","direction":"X","count":4,"spacing":20}}'
        '],"outputs":{}}'
    )


def featureplan_with_operation_name_metadata_paths_json() -> str:
    return (
        '{"version":"2.0","unit":"mm","document_type":"part","part_name":"metadata_op_name_plan",'
        '"metadata":{"name":"metadata_op_name_plan","source":"local","inferred_parameters":[],'
        '"explicit_parameters":["create_new_part.params.part_name","create_sketch.params.name","create_sketch.params.plane",'
        '"sketch_center_rectangle.params.length","sketch_center_rectangle.params.width","extrude_boss.params.depth",'
        '"create_through_hole.params.plane","create_through_hole.params.center","create_through_hole.params.diameter"]},'
        '"operations":['
        '{"id":"1","op":"create_new_part","params":{"part_name":"metadata_op_name_plan"}},'
        '{"id":"2","op":"create_sketch","params":{"name":"BaseSketch","plane":"Top"}},'
        '{"id":"3","op":"sketch_center_rectangle","params":{"sketch":"BaseSketch","center":[0,0],"length":120,"width":80}},'
        '{"id":"4","op":"extrude_boss","params":{"sketch":"BaseSketch","depth":12}},'
        '{"id":"5","op":"create_through_hole","params":{"plane":"top_face","center":[-40,0],"diameter":6}},'
        '{"id":"6","op":"create_linear_pattern","params":{"seed_feature":"Hole1","direction":"X","count":4,"spacing":20}}'
        '],"outputs":{}}'
    )


def featureplan_explicit_operation_name_center_out_of_bounds_json() -> str:
    return (
        '{"version":"2.0","unit":"mm","document_type":"part","part_name":"bad_explicit_center",'
        '"metadata":{"name":"bad_explicit_center","source":"local","inferred_parameters":[],'
        '"explicit_parameters":["create_new_part.params.part_name","create_through_hole.params.center","create_through_hole.params.diameter"]},'
        '"operations":['
        '{"id":"1","op":"create_new_part","params":{}},'
        '{"id":"2","op":"create_sketch","params":{"name":"BaseSketch","plane":"Top"}},'
        '{"id":"3","op":"sketch_center_rectangle","params":{"sketch":"BaseSketch","center":[0,0],"length":120,"width":80}},'
        '{"id":"4","op":"extrude_boss","params":{"sketch":"BaseSketch","depth":12}},'
        '{"id":"5","op":"create_through_hole","params":{"plane":"top_face","center":[-60,0],"diameter":6}},'
        '{"id":"6","op":"create_linear_pattern","params":{"seed_feature":"Hole1","direction":"X","count":4,"spacing":20}}'
        '],"outputs":{}}'
    )


def featureplan_left_edge_hole_on_boundary_json() -> str:
    return (
        '{"version":"2.0","unit":"mm","document_type":"part","part_name":"bad_edge_hole",'
        '"operations":['
        '{"id":"1","op":"create_new_part","params":{}},'
        '{"id":"2","op":"create_sketch","params":{"name":"BaseSketch","plane":"top_face"}},'
        '{"id":"3","op":"sketch_center_rectangle","params":{"sketch":"BaseSketch","center":[0,0],"length":120,"width":80}},'
        '{"id":"4","op":"extrude_boss","params":{"sketch":"BaseSketch","depth":12}},'
        '{"id":"5","op":"create_through_hole","params":{"plane":"top_face","center":[-60,0],"diameter":6}},'
        '{"id":"6","op":"create_linear_pattern","params":{"seed_feature":"Hole1","direction":"X","count":4,"spacing":20}}'
        '],"outputs":{}}'
    )


def featureplan_linear_pattern_with_axis_json() -> str:
    return (
        '{"version":"2.0","unit":"mm","document_type":"part","part_name":"bad_axis_pattern",'
        '"operations":['
        '{"id":"1","op":"create_new_part","params":{}},'
        '{"id":"2","op":"create_sketch","params":{"name":"BaseSketch","plane":"Top"}},'
        '{"id":"3","op":"sketch_center_rectangle","params":{"sketch":"BaseSketch","center":[0,0],"length":120,"width":80}},'
        '{"id":"4","op":"extrude_boss","params":{"sketch":"BaseSketch","depth":12}},'
        '{"id":"5","op":"create_through_hole","params":{"plane":"top_face","center":[-40,0],"diameter":6}},'
        '{"id":"6","op":"create_axis","params":{"name":"Axis_01","reference_type":"two_planes","references":["auto","Right"]}},'
        '{"id":"7","op":"create_linear_pattern","params":{"seed_feature":"5","direction":"x","count":4,"spacing":20}}'
        '],"outputs":{}}'
    )


def featureplan_explicit_out_of_bounds_hole_json() -> str:
    return (
        '{"version":"2.0","unit":"mm","document_type":"part","part_name":"explicit_bad_edge_hole",'
        '"metadata":{"name":"explicit_bad_edge_hole","source":"local","explicit_parameters":["5.params.center"],"inferred_parameters":[]},'
        '"operations":['
        '{"id":"1","op":"create_new_part","params":{}},'
        '{"id":"2","op":"create_sketch","params":{"name":"BaseSketch","plane":"top_face"}},'
        '{"id":"3","op":"sketch_center_rectangle","params":{"sketch":"BaseSketch","center":[0,0],"length":120,"width":80}},'
        '{"id":"4","op":"extrude_boss","params":{"sketch":"BaseSketch","depth":12}},'
        '{"id":"5","op":"create_through_hole","params":{"plane":"top_face","center":[-60,0],"diameter":6}}'
        '],"outputs":{}}'
    )


def featureplan_bad_custom_property_key_json() -> str:
    return (
        '{"version":"2.0","unit":"mm","document_type":"part","part_name":"bad_property",'
        '"operations":['
        '{"id":"1","op":"create_new_part","params":{}},'
        '{"id":"2","op":"create_sketch","params":{"name":"BaseSketch","plane":"top_face"}},'
        '{"id":"3","op":"sketch_center_rectangle","params":{"sketch":"BaseSketch","center":[0,0],"length":100,"width":60}},'
        '{"id":"4","op":"extrude_boss","params":{"sketch":"BaseSketch","depth":10}},'
        '{"id":"5","op":"set_material","params":{"material":"Aluminum_6061"}},'
        '{"id":"6","op":"set_custom_property","params":{"key":"PartNumber","value":"TEST-P1-001"}},'
        '{"id":"7","op":"set_custom_property","params":{"key":"script","value":"P1 API test part"}}'
        '],"outputs":{}}'
    )


def featureplan_repaired_custom_property_json() -> str:
    return (
        '{"version":"2.0","unit":"mm","document_type":"part","part_name":"repaired_property",'
        '"operations":['
        '{"id":"1","op":"create_new_part","params":{}},'
        '{"id":"2","op":"create_sketch","params":{"name":"BaseSketch","plane":"top_face"}},'
        '{"id":"3","op":"sketch_center_rectangle","params":{"sketch":"BaseSketch","center":[0,0],"length":100,"width":60}},'
        '{"id":"4","op":"extrude_boss","params":{"sketch":"BaseSketch","depth":10}},'
        '{"id":"5","op":"set_material","params":{"material":"Aluminum_6061"}},'
        '{"id":"6","op":"set_custom_property","params":{"key":"PartNumber","value":"TEST-P1-001"}},'
        '{"id":"7","op":"set_custom_property","params":{"key":"Description","value":"P1 API test part"}}'
        '],"outputs":{}}'
    )


def featureplan_material_property_with_hallucinated_boss_json() -> str:
    return (
        '{"version":"2.0","unit":"mm","document_type":"part","part_name":"unnamed_part",'
        '"metadata":{"name":"unnamed_part","source":"local","inferred_parameters":["create_center_boss.params.diameter","create_center_boss.params.height"],"explicit_parameters":["1.params.part_name"]},'
        '"operations":['
        '{"id":"1","op":"create_new_part","params":{"part_name":"TEST-P1-001"}},'
        '{"id":"2","op":"set_material","params":{"material":"Aluminum_6061"}},'
        '{"id":"3","op":"create_sketch","params":{"name":"BaseSketch","plane":"top_face"}},'
        '{"id":"4","op":"sketch_center_rectangle","params":{"sketch":"BaseSketch","center":[0,0],"length":100,"width":60}},'
        '{"id":"5","op":"extrude_boss","params":{"sketch":"BaseSketch","depth":10}},'
        '{"id":"6","op":"create_center_boss","params":{"diameter":30,"height":25}},'
        '{"id":"7","op":"cut_center_hole","params":{"diameter":10,"target":"boss"}},'
        '{"id":"8","op":"set_custom_property","params":{"key":"PartNumber","value":"TEST-P1-001"}},'
        '{"id":"9","op":"set_custom_property","params":{"key":"Description","value":"P1 API test part"}},'
        '{"id":"10","op":"save_sldprt","params":{}}'
        '],"outputs":{}}'
    )


def featureplan_repaired_material_property_only_json() -> str:
    return (
        '{"version":"2.0","unit":"mm","document_type":"part","part_name":"unnamed_part",'
        '"metadata":{"name":"unnamed_part","source":"local","inferred_parameters":[],"explicit_parameters":["1.params.part_name","2.params.material","4.params.length","4.params.width","5.params.depth","8.params.value","9.params.value"]},'
        '"operations":['
        '{"id":"1","op":"create_new_part","params":{"part_name":"TEST-P1-001"}},'
        '{"id":"2","op":"set_material","params":{"material":"Aluminum_6061"}},'
        '{"id":"3","op":"create_sketch","params":{"name":"BaseSketch","plane":"top_face"}},'
        '{"id":"4","op":"sketch_center_rectangle","params":{"sketch":"BaseSketch","center":[0,0],"length":100,"width":60}},'
        '{"id":"5","op":"extrude_boss","params":{"sketch":"BaseSketch","depth":10}},'
        '{"id":"8","op":"set_custom_property","params":{"key":"PartNumber","value":"TEST-P1-001"}},'
        '{"id":"9","op":"set_custom_property","params":{"key":"Description","value":"P1 API test part"}},'
        '{"id":"10","op":"save_sldprt","params":{}}'
        '],"outputs":{}}'
    )



def featureplan_material_spec_only_json() -> str:
    return (
        '{"version":"2.0","unit":"mm","document_type":"part","part_name":"material_spec_case",'
        '"operations":['
        '{"id":"1","op":"create_new_part","params":{}},'
        '{"id":"2","op":"set_material","params":{"material_spec":"Aluminum_6061"}},'
        '{"id":"3","op":"create_sketch","params":{"name":"BaseSketch","plane":"top_face"}},'
        '{"id":"4","op":"sketch_center_rectangle","params":{"sketch":"BaseSketch","center":[0,0],"length":100,"width":60}},'
        '{"id":"5","op":"extrude_boss","params":{"sketch":"BaseSketch","depth":10}}'
        '],"outputs":{}}'
    )

class FakeOpenAIClient:
    captured = {}
    response_text = featureplan_json()
    response_queue = []
    error = None

    def __init__(self, **kwargs):
        FakeOpenAIClient.captured["client_kwargs"] = kwargs
        self.chat = type("Chat", (), {"completions": self.FakeCompletions()})()

    class FakeCompletions:
        def create(self, **kwargs):
            FakeOpenAIClient.captured["create_kwargs"] = kwargs
            if FakeOpenAIClient.error:
                raise FakeOpenAIClient.error

            class Message:
                content = FakeOpenAIClient.response_queue.pop(0) if FakeOpenAIClient.response_queue else FakeOpenAIClient.response_text

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]

            return Response()


class TestLocalProviderRepairSemantics(unittest.TestCase):
    def test_policy_error_summary_uses_semantic_binding_for_side_slots(self):
        from app.providers.local_provider import _policy_error_summary

        prompt = "\u521b\u5efa\u4e00\u4e2a120mm*80mm*15mm\u7684\u5b89\u88c5\u677f\uff0c\u5b89\u88c5\u677f\u6cbf\u5bbd\u5ea6\u65b9\u5411\u5206\u522b\u5728\u8ddd\u79bb\u4e24\u8fb920mm\u5904\u5f002\u4e2a\u5bbd\u5ea6\u4e3a10mm\u7684\u901a\u69fd\u3002"
        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "demo",
            "metadata": {"inferred_parameters": ["side_slots.params.center", "side_slots_2.params.center"]},
            "operations": [
                {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "side_slots", "op": "cut_slot", "params": {"plane": "top_face", "center": [-100, 0], "length": 80, "width": 10, "through_all": True}},
                {"id": "side_slots_2", "op": "cut_slot", "params": {"plane": "top_face", "center": [100, 0], "length": 80, "width": 10, "through_all": True}},
            ],
            "outputs": {},
        }

        summary = _policy_error_summary(plan, prompt)
        self.assertEqual(summary, "")

    def test_policy_repair_checklist_uses_semantic_binding_for_pocket_center_phrase(self):
        from app.providers.local_provider import _policy_error_summary

        prompt = "\u518d\u4ece\u5b89\u88c5\u677f\u4e0a\u8868\u9762\u7684\u957f\u8fb9\u65b9\u5411\u7684\u4e2d\u5fc3\u4f4d\u7f6e\u5207\u5272\u4e00\u4e2a10mm*10mm*10mm\u7684\u53e3\u888b"
        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "demo",
            "metadata": {"inferred_parameters": ["pocket.params.center"]},
            "operations": [
                {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "pocket", "op": "cut_rectangle_pocket", "params": {"plane": "top_face", "center": [80, 0], "length": 10, "width": 10, "depth": 10}},
            ],
            "outputs": {},
        }

        summary = _policy_error_summary(plan, prompt)
        self.assertEqual(summary, "")



class TestLocalProvider(unittest.TestCase):
    def setUp(self):
        FakeOpenAIClient.captured = {}
        FakeOpenAIClient.response_text = featureplan_json()
        FakeOpenAIClient.response_queue = []
        FakeOpenAIClient.error = None

    def _parse_local(self, env=None):
        base_env = {
            "AI_SW_LLM_PROVIDER": "local",
            "OPENAI_API_KEY": "",
            "AI_SW_LOCAL_LLM_API_KEY": "local-test-key",
        }
        if env:
            base_env.update(env)
        with patch.dict("os.environ", base_env, clear=True):
            with patch.object(local_provider, "_openai_client_class", return_value=FakeOpenAIClient):
                return local_provider.parse_featureplan("create a 120x80x12 base plate")

    def test_tc_local_001_provider_local_is_selected(self):
        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "local", "AI_SW_LOCAL_LLM_REPAIR_ATTEMPTS": "2"}, clear=True):
            self.assertEqual(current_provider_name(), "local")

    def test_tc_local_002_local_provider_does_not_need_openai_api_key(self):
        plan = self._parse_local({"OPENAI_API_KEY": ""})

        self.assertEqual(plan["operations"][0]["op"], "create_base_plate")

    def test_tc_local_003_local_provider_uses_base_url_env(self):
        self._parse_local({"AI_SW_LOCAL_LLM_BASE_URL": "http://127.0.0.1:11434/v1"})

        self.assertEqual(FakeOpenAIClient.captured["client_kwargs"]["base_url"], "http://127.0.0.1:11434/v1")

    def test_tc_local_004_local_provider_uses_model_env(self):
        self._parse_local({"AI_SW_LOCAL_LLM_MODEL": "qwen2.5-coder:7b-custom"})

        self.assertEqual(FakeOpenAIClient.captured["create_kwargs"]["model"], "qwen2.5-coder:7b-custom")
        self.assertEqual(FakeOpenAIClient.captured["create_kwargs"]["temperature"], 0)

    def test_local_system_prompt_enforces_json_only_no_markdown(self):
        self._parse_local()
        system_prompt = FakeOpenAIClient.captured["create_kwargs"]["messages"][0]["content"]

        self.assertIn("Output JSON only.", system_prompt)
        self.assertIn("Do not output markdown.", system_prompt)
        self.assertIn("Do not output explanations.", system_prompt)
        self.assertIn("Do not output ```json.", system_prompt)
        self.assertIn("The first character must be {.", system_prompt)
        self.assertIn("The last character must be }.", system_prompt)

    def test_local_system_prompt_allows_required_defaults_without_extra_capabilities(self):
        self._parse_local()
        system_prompt = FakeOpenAIClient.captured["create_kwargs"]["messages"][0]["content"]

        self.assertIn("implemented operation set described below", system_prompt)
        self.assertIn("Use only the implemented operations described below", system_prompt)
        self.assertIn("Implemented operations:", system_prompt)
        self.assertIn("create_base_plate", system_prompt)

    def test_local_system_prompt_omits_material_catalog_for_non_material_request(self):
        self._parse_local()
        system_prompt = FakeOpenAIClient.captured["create_kwargs"]["messages"][0]["content"]

        self.assertNotIn("Official SOLIDWORKS material catalog:", system_prompt)

    def test_local_provider_uses_stage_specific_first_pass_timeout_and_num_predict(self):
        self._parse_local({"AI_SW_LOCAL_LLM_TIMEOUT_SECONDS_FIRST": "61", "AI_SW_LOCAL_LLM_NUM_PREDICT_FIRST": "333"})

        self.assertEqual(FakeOpenAIClient.captured["client_kwargs"]["timeout_seconds"], 61.0)
        self.assertEqual(FakeOpenAIClient.captured["create_kwargs"]["extra_body"]["num_predict"], 333)

    def test_local_provider_uses_stage_specific_repair_timeout_and_num_predict(self):
        FakeOpenAIClient.response_queue = [
            featureplan_json().replace('"unit":"mm"', '"unit":"inch"'),
            featureplan_json(),
        ]

        with patch.dict(
            "os.environ",
            {
                "AI_SW_LLM_PROVIDER": "local",
                "AI_SW_LOCAL_LLM_TIMEOUT_SECONDS_REPAIR": "17",
                "AI_SW_LOCAL_LLM_NUM_PREDICT_REPAIR": "123",
            },
            clear=True,
        ):
            with patch.object(local_provider, "_openai_client_class", return_value=FakeOpenAIClient):
                parse_featureplan_with_provider("120x80x12mm")

        self.assertEqual(FakeOpenAIClient.captured["client_kwargs"]["timeout_seconds"], 17.0)
        self.assertEqual(FakeOpenAIClient.captured["create_kwargs"]["extra_body"]["num_predict"], 123)
    def test_local_system_prompt_distinguishes_chamfer_from_fillet(self):
        self._parse_local()
        system_prompt = FakeOpenAIClient.captured["create_kwargs"]["messages"][0]["content"]

        self.assertIn("C2", system_prompt)
        self.assertIn("add_chamfer", system_prompt)
        self.assertIn("Chinese", system_prompt)
        self.assertIn("R2", system_prompt)
        self.assertIn("add_fillet", system_prompt)
        self.assertIn("Chinese", system_prompt)

    def test_local_system_prompt_uses_fast_implemented_only_prompt(self):
        self._parse_local()
        system_prompt = FakeOpenAIClient.captured["create_kwargs"]["messages"][0]["content"]

        self.assertIn("Implemented operations:", system_prompt)
        self.assertNotIn("Blocked non-implemented operations:", system_prompt)
        self.assertIn("status=implemented", system_prompt)

    def test_local_system_prompt_constrains_cut_center_hole_without_plane_or_center(self):
        self._parse_local()
        system_prompt = FakeOpenAIClient.captured["create_kwargs"]["messages"][0]["content"]

        self.assertIn("do not output plane or center", system_prompt)
        self.assertIn("cut_center_hole may use only diameter plus optional depth/through_all/target", system_prompt)
    def test_local_system_prompt_forbids_center_hole_as_pattern_seed(self):
        self._parse_local()
        system_prompt = FakeOpenAIClient.captured["create_kwargs"]["messages"][0]["content"]

        self.assertIn("If a hole will be patterned", system_prompt)
        self.assertIn("Do not use cut_center_hole as a pattern or mirror seed", system_prompt)


    def test_local_system_prompt_reuses_shared_enterprise_featureplan_guidance(self):
        self._parse_local()
        system_prompt = FakeOpenAIClient.captured["create_kwargs"]["messages"][0]["content"]

        self.assertIn("Shared enterprise Feature Registry and Policy guidance:", system_prompt)
        self.assertIn("Use the Feature Registry as the source of truth for matching user intent to operations.", system_prompt)
        self.assertIn("For a hole in the center raised boss/platform, use cut_center_hole target='boss' after create_center_boss.", system_prompt)
        self.assertIn("Do not add corner-hole operations unless the user explicitly requests corner holes", system_prompt)
    def test_local_provider_passes_timeout_to_ollama_client(self):
        self._parse_local({"AI_SW_LOCAL_LLM_TIMEOUT_SECONDS": "12"})

        self.assertEqual(FakeOpenAIClient.captured["client_kwargs"]["timeout_seconds"], 12.0)
        # Standard-library Ollama client uses urllib directly: no http_client / max_retries kwargs.
        self.assertNotIn("http_client", FakeOpenAIClient.captured["client_kwargs"])
        self.assertNotIn("max_retries", FakeOpenAIClient.captured["client_kwargs"])

    def test_tc_local_005_pure_json_response_parses(self):
        FakeOpenAIClient.response_text = featureplan_json()

        plan = self._parse_local()

        self.assertEqual(plan["version"], "2.0")
        self.assertEqual(plan["unit"], "mm")

    def test_tc_local_006_json_markdown_fence_is_stripped(self):
        FakeOpenAIClient.response_text = "```json\n" + featureplan_json() + "\n```"

        plan = self._parse_local()

        self.assertEqual(plan["operations"][0]["op"], "create_base_plate")

    def test_tc_local_007_surrounding_text_json_is_extracted(self):
        FakeOpenAIClient.response_text = "Here is the plan:\n" + featureplan_json() + "\nDone."

        plan = self._parse_local()

        self.assertEqual(plan["part_name"], "local_part")

    def test_tc_local_008_invalid_json_falls_back_to_rule_based(self):
        FakeOpenAIClient.response_text = "not json"
        output = io.StringIO()

        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "local"}, clear=True):
            with patch.object(local_provider, "_openai_client_class", return_value=FakeOpenAIClient):
                with redirect_stdout(output):
                    plan = parse_featureplan_with_provider("120x80x12mm")

        self.assertEqual(plan["operations"][0]["op"], "create_base_plate")
        self.assertIn("fallback to rule_based parser", output.getvalue())

    def test_local_empty_unit_is_protocol_normalized_without_semantic_fallback(self):
        FakeOpenAIClient.response_queue = [featureplan_json().replace('"unit":"mm"', '"unit":""')]
        output = io.StringIO()

        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "local"}, clear=True):
            with patch.object(local_provider, "_openai_client_class", return_value=FakeOpenAIClient):
                with redirect_stdout(output):
                    plan = parse_featureplan_with_provider("120x80x12mm")

        self.assertEqual(plan["operations"][0]["op"], "create_base_plate")
        self.assertEqual(plan["unit"], "mm")
        self.assertNotIn("Local LLM FeaturePlan rejected by Policy Engine", output.getvalue())
        self.assertNotIn("fallback to rule_based parser", output.getvalue())

    def test_local_policy_rejected_featureplan_is_repaired_by_local_llm(self):
        FakeOpenAIClient.response_queue = [
            featureplan_json().replace('"unit":"mm"', '"unit":"inch"'),
            featureplan_json(),
        ]
        output = io.StringIO()

        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "local"}, clear=True):
            with patch.object(local_provider, "_openai_client_class", return_value=FakeOpenAIClient):
                with redirect_stdout(output):
                    plan = parse_featureplan_with_provider("120x80x12mm")

        self.assertEqual(plan["operations"][0]["op"], "create_base_plate")
        self.assertEqual(plan["unit"], "mm")
        self.assertIn("Local LLM FeaturePlan rejected by Policy Engine", output.getvalue())
        self.assertIn("requesting local model repair", output.getvalue())
        self.assertNotIn("fallback to rule_based parser", output.getvalue())
        self.assertEqual(len(FakeOpenAIClient.captured["create_kwargs"]["messages"]), 2)
        repair_prompt = FakeOpenAIClient.captured["create_kwargs"]["messages"][1]["content"]
        self.assertIn("SolidWorks mechanical modeling task", repair_prompt)
        self.assertIn("equipment parts", repair_prompt)
        self.assertIn("recommend reasonable missing parameters", repair_prompt)
        self.assertIn("Keep all inferred lengths in mm", repair_prompt)
        self.assertIn("Do not add optional parameters", repair_prompt)
        self.assertIn('Set the top-level field "unit" exactly to "mm"', repair_prompt)
        self.assertIn("Required fixes:", repair_prompt)

    def test_local_planning_rejected_featureplan_is_repaired_by_local_llm(self):
        FakeOpenAIClient.response_queue = [
            featureplan_missing_base_solid_json(),
            featureplan_repaired_offcenter_hole_json(),
        ]
        output = io.StringIO()

        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "local"}, clear=True):
            with patch.object(local_provider, "_openai_client_class", return_value=FakeOpenAIClient):
                with redirect_stdout(output):
                    plan = parse_featureplan_with_provider("鐎归潻缂氶弲鑸垫綇閸︻厾鍠?0mm濠㈣泛瀚槐鎴犫偓娑欐煥閼荤喖姊奸棃娑樼仚")

        self.assertEqual(plan["operations"][3]["op"], "extrude_boss")
        self.assertEqual(plan["operations"][4]["op"], "create_through_hole")
        self.assertEqual(plan["operations"][4]["params"]["center"], [-40, 0])
        self.assertIn("Local LLM FeaturePlan rejected by Policy Engine", output.getvalue())
        repair_prompt = FakeOpenAIClient.captured["create_kwargs"]["messages"][1]["content"]
        self.assertIn("completed base solid", repair_prompt)
        self.assertIn("off-center positioned hole", repair_prompt)
        self.assertIn("actual FeaturePlan dimensions", repair_prompt)
        self.assertIn("Determine the active coordinate system", repair_prompt)
        self.assertIn("change the hole operation type itself to create_through_hole or create_blind_hole", repair_prompt)
        self.assertIn("Do not try to repair this by adding center or plane parameters to cut_center_hole", repair_prompt)

    def test_local_boundary_rejected_featureplan_is_repaired_by_local_llm(self):
        FakeOpenAIClient.response_queue = [
            featureplan_left_edge_hole_on_boundary_json(),
        ]
        output = io.StringIO()

        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "local", "AI_SW_LOCAL_LLM_REPAIR_ATTEMPTS": "2"}, clear=True):
            with patch.object(local_provider, "_openai_client_class", return_value=FakeOpenAIClient):
                with redirect_stdout(output):
                    plan = parse_featureplan_with_provider("create a 120x80x12 plate with a 6mm hole 20mm from the left edge")

        # Deterministic binding repairs the out-of-bounds (non-explicit) hole
        # center on the first pass, so no LLM repair round-trip is needed.
        self.assertEqual(plan["operations"][4]["op"], "create_through_hole")
        self.assertEqual(plan["operations"][4]["params"]["center"], [-40, 0])
        self.assertIn("5.params.center", plan["metadata"]["inferred_parameters"])
        self.assertNotIn("Local LLM FeaturePlan rejected by Policy Engine", output.getvalue())

    def test_local_boundary_repair_gets_second_attempt_when_provenance_is_still_missing(self):
        FakeOpenAIClient.response_queue = [
            featureplan_left_edge_hole_on_boundary_json(),
        ]
        output = io.StringIO()

        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "local", "AI_SW_LOCAL_LLM_REPAIR_ATTEMPTS": "2"}, clear=True):
            with patch.object(local_provider, "_openai_client_class", return_value=FakeOpenAIClient):
                with redirect_stdout(output):
                    plan = parse_featureplan_with_provider("create a 120x80x12 plate with a 6mm hole 20mm from the left edge")

        # The deterministic center fix is recorded as an inferred parameter so
        # the Policy Engine boundary/provenance check passes without any repair.
        self.assertEqual(plan["operations"][4]["params"]["center"], [-40, 0])
        self.assertIn("5.params.center", plan["metadata"]["inferred_parameters"])
        self.assertNotIn("Local LLM repair still invalid", output.getvalue())

    def test_local_create_axis_policy_error_repair_prompt_removes_unrequested_reference_geometry(self):
        FakeOpenAIClient.response_queue = [
            featureplan_linear_pattern_with_axis_json(),
            featureplan_repaired_offcenter_hole_json(),
        ]
        output = io.StringIO()

        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "local"}, clear=True):
            with patch.object(local_provider, "_openai_client_class", return_value=FakeOpenAIClient):
                with redirect_stdout(output):
                    plan = parse_featureplan_with_provider("create a 120x80x12 plate with a 6mm hole 20mm from the left edge and pattern it along x")

        self.assertEqual(plan["operations"][4]["op"], "create_through_hole")
        repair_prompt = FakeOpenAIClient.captured["create_kwargs"]["messages"][1]["content"]
        self.assertIn("Do not invent create_axis to satisfy a linear pattern", repair_prompt)
        self.assertIn("remove create_axis", repair_prompt)
        self.assertIn("params.direction set directly to x, y, or z", repair_prompt)
        self.assertIn("Local LLM FeaturePlan rejected by Policy Engine", output.getvalue())
    def test_local_prompt_maps_m6_corner_holes_to_numeric_6_6(self):
        self._parse_local()
        system_prompt = FakeOpenAIClient.captured["create_kwargs"]["messages"][0]["content"]

        self.assertIn("Interpret M6 clearance holes, M6 bolt holes, and M6 corner holes as diameter=6.6 mm", system_prompt)
        self.assertIn("always output a numeric diameter", system_prompt)
    def test_local_prompt_constrains_cut_corner_holes_to_positive_edge_distances(self):
        self._parse_local()
        system_prompt = FakeOpenAIClient.captured["create_kwargs"]["messages"][0]["content"]

        self.assertIn("Never output negative values for cut_corner_holes", system_prompt)
        self.assertIn("edge_margin, offset_x, and offset_y are positive distances", system_prompt)

    def test_local_cut_corner_holes_missing_diameter_repair_prompt_uses_m6_clearance(self):
        repair_prompt = local_provider._repair_messages(
            "plate with four corner M6 holes",
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "bad_corner_holes",
                "operations": [
                    {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 12, "plane": "Top"}},
                    {"id": "hole_001", "op": "cut_corner_holes", "params": {"edge_margin": 10}},
                ],
                "outputs": {},
            },
            "parameters: 缂傚搫鐨箛鍛存付閸欏倹鏆? diameter; geometry: 閸ユ稖顫楃€?diameter 韫囧懘銆忔径褌绨?0",
        )[1]["content"]

        self.assertIn("repair diameter to the numeric clearance-hole value 6.6 mm", repair_prompt)
        self.assertIn("Never leave M6 as text", repair_prompt)
    def test_local_cut_corner_holes_negative_offset_repair_prompt_prefers_positive_edge_distances(self):
        repair_prompt = local_provider._repair_messages(
            "plate with four corner M6 holes 10mm from each edge",
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "bad_corner_holes",
                "operations": [
                    {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 12, "plane": "Top"}},
                    {"id": "hole_001", "op": "cut_corner_holes", "params": {"diameter": 6.6, "offset_x": -59, "offset_y": -39}},
                ],
                "outputs": {},
            },
            "geometry: 鐏忓搫顕稉宥堝厴娑撻缚绀嬮弫? -59.0; geometry: 鐏忓搫顕稉宥堝厴娑撻缚绀嬮弫? -39.0; geometry: 閸ユ稖顫楃€?offset_x 韫囧懘銆忔径褌绨?0; geometry: 閸ユ稖顫楃€?offset_y 韫囧懘銆忔径褌绨?0",
        )[1]["content"]

        self.assertIn("offset_x and offset_y must be positive distances", repair_prompt)
        self.assertIn("prefer cut_corner_holes edge_margin", repair_prompt)
        self.assertIn("Never output negative signed coordinates for corner holes", repair_prompt)
    def test_local_cut_center_hole_parameter_repair_prompt_removes_plane_and_center(self):
        repair_prompt = local_provider._repair_messages(
            "plate with center boss and center through hole",
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "bad_center_hole",
                "operations": [
                    {"id": "boss_001", "op": "create_center_boss", "params": {"diameter": 30, "height": 25}},
                    {"id": "hole_001", "op": "cut_center_hole", "params": {"diameter": 10, "plane": "top_face", "center": [0, 0]}},
                ],
                "outputs": {},
            },
            "parameters: 閸欏倹鏆熼張顏勬躬閻ц棄鎮曢崡鏇氳厬: center; parameters: 閸欏倹鏆熼張顏勬躬閻ц棄鎮曢崡鏇氳厬: plane",
        )[1]["content"]

        self.assertIn("remove params.center and params.plane", repair_prompt)
        self.assertIn("cut_center_hole target=boss", repair_prompt)
        self.assertIn("cut_center_hole target=base", repair_prompt)
    def test_local_plane_policy_error_repair_prompt_uses_exact_controlled_selectors(self):
        FakeOpenAIClient.response_queue = [
            featureplan_invalid_plane_offcenter_hole_json(),
            featureplan_repaired_offcenter_hole_json(),
        ]
        output = io.StringIO()

        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "local"}, clear=True):
            with patch.object(local_provider, "_openai_client_class", return_value=FakeOpenAIClient):
                with redirect_stdout(output):
                    plan = parse_featureplan_with_provider("create a 120x80x12 plate with a 6mm hole 20mm from the left edge")

        self.assertEqual(plan["operations"][1]["params"]["plane"], "Top")
        self.assertEqual(plan["operations"][4]["params"]["plane"], "top_face")
        self.assertNotIn("Local LLM FeaturePlan rejected by Policy Engine", output.getvalue())
        self.assertNotIn("Local LLM repair still invalid", output.getvalue())

    def test_local_operation_name_explicit_center_boundary_error_is_repaired_not_confirmed(self):
        FakeOpenAIClient.response_queue = [
            featureplan_explicit_operation_name_center_out_of_bounds_json(),
            featureplan_repaired_offcenter_hole_json(),
        ]
        output = io.StringIO()

        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "local"}, clear=True):
            with patch.object(local_provider, "_openai_client_class", return_value=FakeOpenAIClient):
                with redirect_stdout(output):
                    plan = parse_featureplan_with_provider("create a 120x80x12 plate with a 6mm hole 20mm from the left edge")

        self.assertEqual(plan["operations"][4]["params"]["center"], [-40, 0])
        self.assertIn("5.params.center", plan["metadata"]["inferred_parameters"])
        self.assertNotIn("Local LLM FeaturePlan rejected by Policy Engine", output.getvalue())

    def test_local_protocol_normalizes_unique_metadata_operation_name_paths(self):
        FakeOpenAIClient.response_queue = [featureplan_with_operation_name_metadata_paths_json()]

        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "local"}, clear=True):
            with patch.object(local_provider, "_openai_client_class", return_value=FakeOpenAIClient):
                plan = parse_featureplan_with_provider("create a 120x80x12 plate with a 6mm hole 20mm from the left edge")

        explicit = plan["metadata"]["explicit_parameters"]
        self.assertIn("1.params.part_name", explicit)
        self.assertIn("2.params.name", explicit)
        self.assertNotIn("5.params.center", explicit)
        self.assertNotIn("create_through_hole.params.center", explicit)

    def test_local_protocol_drops_missing_or_center_operation_name_explicit_metadata_paths(self):
        data = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "metadata_noise",
            "metadata": {
                "explicit_parameters": [
                    "create_new_part.params.part_name",
                    "create_through_hole.params.center",
                    "create_through_hole.params.diameter",
                ],
            },
            "operations": [
                {"id": "1", "op": "create_new_part", "params": {}},
                {"id": "5", "op": "create_through_hole", "params": {"plane": "top_face", "center": [-60, 0], "diameter": 6}},
            ],
            "outputs": {},
        }

        normalized = local_provider._normalize_featureplan_protocol(data)

        explicit = normalized["metadata"]["explicit_parameters"]
        self.assertNotIn("create_new_part.params.part_name", explicit)
        self.assertNotIn("create_through_hole.params.center", explicit)
        self.assertIn("5.params.diameter", explicit)

    def test_local_protocol_drops_ambiguous_metadata_operation_name_paths(self):
        data = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "ambiguous_metadata",
            "metadata": {"explicit_parameters": ["create_sketch.params.name"]},
            "operations": [
                {"id": "1", "op": "create_sketch", "params": {"name": "A", "plane": "Top"}},
                {"id": "2", "op": "create_sketch", "params": {"name": "B", "plane": "Front"}},
            ],
            "outputs": {},
        }

        normalized = local_provider._normalize_featureplan_protocol(data)

        self.assertNotIn("create_sketch.params.name", normalized["metadata"]["explicit_parameters"])

    def test_local_protocol_normalizes_inferred_operation_name_paths(self):
        data = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "inferred_metadata",
            "metadata": {"inferred_parameters": ["create_center_boss.params.diameter"], "explicit_parameters": []},
            "operations": [
                {"id": "1", "op": "create_center_boss", "params": {"diameter": 30, "height": 25}},
            ],
            "outputs": {},
        }

        normalized = local_provider._normalize_featureplan_protocol(data)

        self.assertIn("1.params.diameter", normalized["metadata"]["inferred_parameters"])

    def test_local_protocol_compresses_opname_id_joined_provenance_paths(self):
        # Local 7B often joins the operation name and id with a dot, producing a
        # 4-segment provenance path (``create_base_plate.001.params.plane``) that
        # the Policy Engine rejects. It must be compressed to the canonical
        # ``<id>.params.<param>`` form, and references to non-existent
        # operations/params must be dropped rather than passed through.
        data = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "joined_paths",
            "metadata": {
                "inferred_parameters": [
                    "create_base_plate.001.params.plane",
                    "create_center_boss.006.params.host",
                    "cut_center_hole.007.params.depth",
                ],
                "explicit_parameters": [],
            },
            "operations": [
                {"id": "001", "op": "create_base_plate", "params": {"length": 100, "width": 80, "thickness": 10, "plane": "Top"}},
                {"id": "006", "op": "create_center_boss", "params": {"diameter": 30, "height": 20}},
            ],
            "outputs": {},
        }

        normalized = local_provider._normalize_featureplan_protocol(data)
        paths = (
            normalized["metadata"]["inferred_parameters"]
            + normalized["metadata"]["explicit_parameters"]
        )

        # Valid path is compressed to canonical 3-segment id form.
        self.assertIn("001.params.plane", paths)
        # Reference to a param the op does not have (host) is dropped.
        self.assertNotIn("create_center_boss.006.params.host", paths)
        # Reference to a non-existent operation is dropped.
        self.assertNotIn("cut_center_hole.007.params.depth", paths)
        # Every surviving path is a valid 3-segment ``<id>.params.<param>`` form.
        for path in paths:
            segments = path.split(".")
            self.assertEqual(len(segments), 3)
            self.assertEqual(segments[1], "params")

    def test_local_protocol_normalizes_center_object_and_metadata_center_components(self):
        data = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "center_object_case",
            "metadata": {
                "explicit_parameters": [
                    "create_through_hole_001.params.center.x",
                    "create_through_hole_001.params.center.y",
                    "create_through_hole_001.params.diameter",
                    "create_through_hole_001.params.plane",
                ],
                "inferred_parameters": [],
            },
            "operations": [
                {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 12, "plane": "Top"}},
                {"id": "hole_001", "op": "create_through_hole", "params": {"plane": "top_face", "center": {"x": -40, "y": 0}, "diameter": 6}},
            ],
            "outputs": {},
        }

        normalized = local_provider._normalize_featureplan_protocol(data)

        self.assertEqual(normalized["operations"][1]["params"]["center"], [-40, 0])
        explicit = normalized["metadata"]["explicit_parameters"]
        self.assertNotIn("hole_001.params.center", explicit)
        self.assertIn("hole_001.params.diameter", explicit)
        self.assertIn("hole_001.params.plane", explicit)
        self.assertNotIn("create_through_hole_001.params.center.x", explicit)
        self.assertNotIn("create_through_hole_001.params.center.y", explicit)

    def test_local_explicit_out_of_bounds_featureplan_requires_confirmation_without_repair(self):
        FakeOpenAIClient.response_queue = [featureplan_explicit_out_of_bounds_hole_json()]

        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "local"}, clear=True):
            with patch.object(local_provider, "_openai_client_class", return_value=FakeOpenAIClient):
                with self.assertRaises(local_provider.LocalProviderConfirmationRequired):
                    local_provider.parse_featureplan("create a plate with explicit coordinate x=-60")

        self.assertFalse(FakeOpenAIClient.response_queue)

    def test_local_policy_repair_failure_does_not_fallback_to_rule_based(self):
        FakeOpenAIClient.response_queue = [
            featureplan_json().replace('"unit":"mm"', '"unit":"inch"'),
            featureplan_json().replace('"unit":"mm"', '"unit":"inch"'),
            featureplan_json().replace('"unit":"mm"', '"unit":"inch"'),
        ]
        output = io.StringIO()

        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "local"}, clear=True):
            with patch.object(local_provider, "_openai_client_class", return_value=FakeOpenAIClient):
                with redirect_stdout(output):
                    with self.assertRaises(Exception):
                        parse_featureplan_with_provider("120x80x12mm")

        self.assertIn("Local LLM output invalid after repair", output.getvalue())
        self.assertNotIn("LLM provider: rule_based", output.getvalue())

    def test_local_protocol_normalizes_invalid_part_name(self):
        data = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "Installation Plate",
            "metadata": {"name": "Installation Plate"},
            "operations": [],
            "outputs": {},
        }

        normalized = local_provider._normalize_featureplan_protocol(data)

        self.assertEqual(normalized["part_name"], "Installation_Plate")
        self.assertEqual(normalized["metadata"]["name"], "Installation_Plate")

    def test_local_protocol_expands_multi_instance_operation_params_list(self):
        data = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "multi_slot_case",
            "operations": [
                {"id": "side_slots", "op": "cut_slot", "params": [
                    {"plane": "top_face", "center": [-30, 0], "length": 80, "width": 10},
                    {"plane": "top_face", "center": [30, 0], "length": 80, "width": 10},
                ]},
            ],
            "outputs": [{"op": "save_sldprt"}],
        }

        normalized = local_provider._normalize_featureplan_protocol(data)

        self.assertEqual(len(normalized["operations"]), 2)
        self.assertEqual(normalized["operations"][0]["id"], "side_slots_001")
        self.assertEqual(normalized["operations"][1]["id"], "side_slots_002")
        self.assertEqual(normalized["operations"][0]["params"]["center"], [-30, 0])
        self.assertEqual(normalized["operations"][1]["params"]["center"], [30, 0])
        self.assertEqual(normalized["outputs"], {"save_sldprt": True})

    def test_local_protocol_normalizes_metadata_dict_buckets_and_outputs_array(self):
        data = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "array_outputs_case",
            "metadata": {
                "explicit_parameters": {
                    "create_base_plate.params.length": 120,
                    "create_base_plate.params.width": True,
                },
                "inferred_parameters": {
                    "add_fillet.params.radius": 3,
                },
            },
            "operations": [
                {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "top_face"}},
                {"id": "fillet_001", "op": "add_fillet", "params": {"radius": 3, "target": "outer_edges"}},
            ],
            "outputs": [
                {"operation_id": "save_sldprt", "description": "Save the final model as an SLDPRT file."},
                {"operation_id": "export_step", "description": "Export the final model in STEP format."},
            ],
        }

        normalized = local_provider._normalize_featureplan_protocol(data)

        self.assertEqual(normalized["metadata"]["explicit_parameters"], ["base_001.params.length", "base_001.params.width"])
        self.assertEqual(normalized["metadata"]["inferred_parameters"], ["fillet_001.params.radius", "fillet_001.params.target"])
        self.assertEqual(normalized["outputs"], {"save_sldprt": True, "export_step": True})
        self.assertEqual(normalized["operations"][0]["params"]["plane"], "top_face")


    def test_local_protocol_autofills_inferred_provenance_for_repaired_safe_params(self):
        data = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "repaired_provenance_case",
            "metadata": {
                "explicit_parameters": {
                    "create_base_plate.params.length": 120,
                    "create_base_plate.params.width": 80,
                    "create_base_plate.params.thickness": 15,
                },
                "inferred_parameters": {
                    "cut_corner_holes.params.diameter": 10,
                },
            },
            "operations": [
                {"id": "base_plate_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "corner_holes_001", "op": "cut_corner_holes", "params": {"diameter": 10, "edge_margin": 15}},
                {"id": "fillet_001", "op": "add_fillet", "params": {"radius": 3, "target": "outer_edges"}},
            ],
            "outputs": [],
        }

        normalized = local_provider._normalize_featureplan_protocol(data)

        inferred = normalized["metadata"]["inferred_parameters"]
        self.assertIn("corner_holes_001.params.edge_margin", inferred)
        self.assertIn("fillet_001.params.radius", inferred)
        self.assertIn("fillet_001.params.target", inferred)
    def test_local_protocol_moves_top_level_rebuild_fields_into_operations(self):
        data = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "rebuild_case",
            "operations": [
                {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 12, "plane": "Top"}},
            ],
            "rebuild_model": True,
            "validate_rebuild": {"requested": True},
            "outputs": {},
        }

        normalized = local_provider._normalize_featureplan_protocol(data)
        ops = [operation["op"] for operation in normalized["operations"]]

        self.assertIn("rebuild_model", ops)
        self.assertIn("validate_rebuild", ops)
        self.assertNotIn("rebuild_model", normalized)
        self.assertNotIn("validate_rebuild", normalized)

    def test_local_protocol_moves_top_level_output_flags_into_outputs(self):
        data = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "output_case",
            "operations": [],
            "save_sldprt": True,
            "export_step": {"requested": True},
            "capture_png": False,
        }

        normalized = local_provider._normalize_featureplan_protocol(data)

        self.assertEqual(
            normalized["outputs"],
            {"save_sldprt": True, "export_step": True, "capture_png": False},
        )
        self.assertNotIn("save_sldprt", normalized)
        self.assertNotIn("export_step", normalized)
        self.assertNotIn("capture_png", normalized)

    def test_local_protocol_normalizes_set_material_material_spec_to_material(self):
        data = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "material_spec_case",
            "operations": [
                {"id": "1", "op": "create_new_part", "params": {}},
                {"id": "2", "op": "set_material", "params": {"material_spec": "Aluminum_6061"}},
            ],
            "outputs": {},
        }

        normalized = local_provider._normalize_featureplan_protocol(data)

        params = normalized["operations"][1]["params"]
        self.assertEqual(params["material"], "Aluminum_6061")
        self.assertNotIn("material_spec", params)

    def test_local_material_spec_parameter_prompt_and_protocol_use_catalog_material_field(self):
        plan = local_provider._normalize_featureplan_protocol({
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "material_spec_case",
            "operations": [
                {"id": "1", "op": "create_new_part", "params": {}},
                {"id": "2", "op": "set_material", "params": {"material_spec": "Aluminum_6061"}},
            ],
            "outputs": {},
        })

        self.assertEqual(plan["operations"][1]["params"]["material"], "Aluminum_6061")
        self.assertNotIn("material_spec", plan["operations"][1]["params"])

        repair_prompt = local_provider._repair_messages(
            "create a 100x60x10mm part, set material Aluminum_6061",
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "material_spec_case",
                "operations": [
                    {"id": "2", "op": "set_material", "params": {"material_spec": "Aluminum_6061"}},
                ],
                "outputs": {},
            },
            "parameters: 缂傚搫鐨箛鍛存付閸欏倹鏆? material; parameters: 閸欏倹鏆熼張顏勬躬閻ц棄鎮曢崡鏇氳厬: material_spec",
        )[1]["content"]

        self.assertIn("Never use params.material_spec", repair_prompt)
        self.assertIn("6061 Alloy", repair_prompt)
        self.assertIn("Aluminum_6061", repair_prompt)
    def test_local_custom_property_dangerous_key_is_repaired_to_allowlisted_key(self):
        FakeOpenAIClient.response_queue = [
            featureplan_bad_custom_property_key_json(),
            featureplan_repaired_custom_property_json(),
        ]
        output = io.StringIO()

        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "local"}, clear=True):
            with patch.object(local_provider, "_openai_client_class", return_value=FakeOpenAIClient):
                with redirect_stdout(output):
                    plan = parse_featureplan_with_provider("material Aluminum_6061, part number TEST-P1-001, description P1 API test part")

        property_ops = [op for op in plan["operations"] if op["op"] == "set_custom_property"]
        self.assertEqual(property_ops[0]["params"]["key"], "PartNumber")
        self.assertEqual(property_ops[1]["params"]["key"], "Description")
        self.assertIn("Local LLM FeaturePlan rejected by Policy Engine", output.getvalue())
        repair_prompt = FakeOpenAIClient.captured["create_kwargs"]["messages"][1]["content"]
        self.assertIn("part number/part no", repair_prompt)
        self.assertIn("PartNumber", repair_prompt)
        self.assertIn("Description", repair_prompt)
        self.assertIn("Description", repair_prompt)
        self.assertIn("Never use script", repair_prompt)

    def test_local_material_property_request_removes_hallucinated_boss_and_hole(self):
        FakeOpenAIClient.response_queue = [
            featureplan_material_property_with_hallucinated_boss_json(),
            featureplan_repaired_material_property_only_json(),
        ]
        output = io.StringIO()

        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "local"}, clear=True):
            with patch.object(local_provider, "_openai_client_class", return_value=FakeOpenAIClient):
                with redirect_stdout(output):
                    plan = parse_featureplan_with_provider(
                        "create a 100x60x10mm part, set material Aluminum_6061, part number TEST-P1-001, description P1 API test part"
                    )

        ops = [operation["op"] for operation in plan["operations"]]
        self.assertIn("set_material", ops)
        self.assertIn("set_custom_property", ops)
        self.assertNotIn("create_center_boss", ops)
        self.assertNotIn("cut_center_hole", ops)
        self.assertNotIn("Local LLM FeaturePlan rejected by Policy Engine", output.getvalue())
        system_prompt = FakeOpenAIClient.captured["create_kwargs"]["messages"][0]["content"]
        self.assertIn("Use only the implemented operations", system_prompt)


    def test_tc_local_009_local_service_unavailable_falls_back_with_message(self):
        FakeOpenAIClient.error = RuntimeError("connection refused")
        output = io.StringIO()

        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "local"}, clear=True):
            with patch.object(local_provider, "_openai_client_class", return_value=FakeOpenAIClient):
                with redirect_stdout(output):
                    plan = parse_featureplan_with_provider("120x80x12mm")

        self.assertEqual(plan["operations"][0]["op"], "create_base_plate")
        self.assertIn("Local LLM unavailable, fallback to rule_based parser", output.getvalue())

    def test_tc_local_010_unknown_provider_falls_back_with_message(self):
        output = io.StringIO()

        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "not_a_provider"}, clear=True):
            with redirect_stdout(output):
                plan = parse_featureplan_with_provider("120x80x12mm")

        self.assertEqual(plan["operations"][0]["op"], "create_base_plate")
        self.assertIn("Unknown AI_SW_LLM_PROVIDER=not_a_provider", output.getvalue())
        self.assertIn("fallback to rule_based parser", output.getvalue())

    def test_tc_local_011_openai_insufficient_quota_suggests_local(self):
        output = io.StringIO()

        with patch.dict("os.environ", {"AI_SW_LLM_PROVIDER": "openai"}, clear=True):
            with patch("app.providers.openai_provider.parse_featureplan", side_effect=RuntimeError("insufficient_quota")):
                with redirect_stdout(output):
                    plan = parse_featureplan_with_provider("120x80x12mm")

        self.assertEqual(plan["operations"][0]["op"], "create_base_plate")
        self.assertIn("OpenAI LLM unavailable", output.getvalue())
        self.assertIn("AI_SW_LLM_PROVIDER=local", output.getvalue())

    def test_tc_local_012_dangerous_fields_are_rejected_by_policy(self):
        for field in DANGEROUS_FIELDS:
            with self.subTest(field=field):
                plan = FeaturePlan.from_dict(
                    {
                        "version": "2.0",
                        "unit": "mm",
                        "document_type": "part",
                        "part_name": "bad_local",
                        "operations": [
                            {
                                "id": "base_001",
                                "op": "create_base_plate",
                                "params": {"length": 120, "width": 80, "thickness": 12, "plane": "Top", field: "bad"},
                            }
                        ],
                        "outputs": {},
                    }
                )
                result = PolicyEngine().validate(plan)
                self.assertFalse(result.allowed)
                self.assertTrue(any(field in violation.message for violation in result.violations), result.violations)

    def test_tc_local_013_local_featureplan_enters_policy_and_dry_run(self):
        plan_dict = self._parse_local()
        featureplan = FeaturePlan.from_dict(plan_dict)

        policy = PolicyEngine().validate(featureplan)
        self.assertTrue(policy.allowed, policy.violations)
        result = SolidWorksApiExecutor().dry_run(featureplan)
        self.assertEqual(result.status, "dry_run")

    def test_tc_local_014_openai_api_key_is_not_read_by_local_provider(self):
        self._parse_local({"OPENAI_API_KEY": "cloud-key-must-not-be-used"})

        self.assertEqual(FakeOpenAIClient.captured["client_kwargs"]["api_key"], "local-test-key")
        self.assertNotEqual(FakeOpenAIClient.captured["client_kwargs"]["api_key"], "cloud-key-must-not-be-used")

    def test_tc_local_015_logs_do_not_leak_complete_keys(self):
        message = safe_exception_message(
            RuntimeError(
                "failed OPENAI_API_KEY=cloud-secret-value "
                "AI_SW_LOCAL_LLM_API_KEY=local-secret-value "
                "api_key=another-secret-value"
            )
        )

        self.assertIn("[redacted]", message)
        self.assertNotIn("cloud-secret-value", message)
        self.assertNotIn("local-secret-value", message)
        self.assertNotIn("another-secret-value", message)


    def test_outputs_prompt_requires_json_object(self):
        initial_prompt = local_provider._local_system_prompt("create a mounting plate")
        repair_prompt = local_provider._repair_system_prompt()

        self.assertIn("outputs MUST be a JSON object", initial_prompt)
        self.assertIn("top-level outputs field MUST be a JSON object", repair_prompt)

    def test_empty_malformed_outputs_are_protocol_normalized_without_semantic_fallback(self):
        for value in (None, "", []):
            with self.subTest(value=value):
                normalized = local_provider._normalize_featureplan_protocol(
                    {
                        "version": "2.0",
                        "unit": "mm",
                        "document_type": "part",
                        "part_name": "test_part",
                        "operations": [],
                        "outputs": value,
                    }
                )
                self.assertEqual(normalized["outputs"], {})

    def test_nonempty_invalid_outputs_are_not_silently_normalized(self):
        normalized = local_provider._normalize_featureplan_protocol(
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "test_part",
                "operations": [],
                "outputs": "save everything",
            }
        )

        self.assertEqual(normalized["outputs"], "save everything")
        result = PolicyEngine().validate(normalized)
        self.assertFalse(result.allowed)
        self.assertTrue(any(violation.code == "outputs" for violation in result.violations))

    def test_protocol_normalization_autofills_missing_center_provenance_as_inferred(self):
        normalized = local_provider._normalize_featureplan_protocol(
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "center_provenance_case",
                "metadata": {"explicit_parameters": [], "inferred_parameters": []},
                "operations": [
                    {"id": "slot_001", "op": "cut_slot", "params": {"plane": "top_face", "center": [10, 0], "length": 40, "width": 10, "through_all": True}},
                ],
                "outputs": {},
            }
        )

        inferred = normalized["metadata"]["inferred_parameters"]
        self.assertIn("slot_001.params.center", inferred)

    def test_local_repair_prompt_guides_slot_pocket_and_fillet_normalization(self):
        repair_prompt = local_provider._repair_messages(
            "Create a 120x80x15mm plate, add two side through slots, a pocket, and R3 fillets.",
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "repair_prompt_case",
                "operations": [],
                "outputs": {},
            },
            "geometry: cut_slot length must be greater than width; geometry: add_fillet target must be outer_edges/top_edges/bottom_edges",
        )[1]["content"]

        self.assertIn("params.length is always the slot span", repair_prompt)
        self.assertIn("move the feature center inward by half of the feature size", repair_prompt)
        self.assertIn("use add_fillet params.target=outer_edges", repair_prompt)

    def test_local_repair_prompt_explicitly_requests_missing_corner_holes_operation(self):
        repair_prompt = local_provider._repair_messages(
            "?????10mm???????????20mm????",
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "repair_prompt_case",
                "operations": [
                    {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                    {"id": "boss_001", "op": "create_center_boss", "params": {"diameter": 20, "height": 15}},
                ],
                "outputs": {},
            },
            "semantic_completeness: missing requested cut_corner_holes operation",
        )[1]["content"]

        self.assertIn("Add exactly one cut_corner_holes operation", repair_prompt)
        self.assertIn("copy that numeric diameter", repair_prompt)
    def test_semantic_binding_normalizes_complex_side_slots_and_pocket_into_base_boundary(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics
        from app.providers.local_provider import _policy_error_summary

        prompt = (
            "Create a 120x80x15mm installation plate, "
            "cut two slots along the width direction from both side edges 20mm with slot width 10mm, "
            "cut a 10x10x10mm pocket from the plate top face center, "
            "and add R3 fillets."
        )
        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "complex_plate",
            "operations": [
                {"id": "base_plate_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "side_slots", "op": "cut_slot", "params": {"plane": "top_face", "length": 40, "width": 10, "center": [0, 80], "through_all": True}},
                {"id": "side_slots_2", "op": "cut_slot", "params": {"plane": "top_face", "length": 40, "width": 10, "center": [0, -80], "through_all": True}},
                {"id": "pocket", "op": "cut_rectangle_pocket", "params": {"plane": "top_face", "length": 10, "width": 10, "depth": 10, "center": [60, 0]}},
                {"id": "fillet_001", "op": "add_fillet", "params": {"radius": 3, "target": "outer_edges"}},
            ],
            "outputs": {},
        }

        bound = bind_featureplan_semantics(prompt, plan)
        slot_1 = next(op for op in bound["operations"] if op["id"] == "side_slots")
        slot_2 = next(op for op in bound["operations"] if op["id"] == "side_slots_2")
        pocket = next(op for op in bound["operations"] if op["id"] == "pocket")

        self.assertEqual(slot_1["params"]["direction"], "y")
        self.assertEqual(slot_2["params"]["direction"], "y")
        self.assertEqual(slot_1["params"]["center"], [-35.0, 0.0])
        self.assertEqual(slot_2["params"]["center"], [35.0, 0.0])
        self.assertEqual(pocket["params"]["center"], [55.0, 0.0])
        self.assertEqual(_policy_error_summary(plan, prompt), "")

    def test_semantic_binding_uses_slot_edge_clearance_not_center_distance(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "slot_clearance_case",
            "operations": [
                {"id": "base_plate", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "side_slots", "op": "cut_slot", "params": {"plane": "top_face", "center": [5, 40], "length": 80, "width": 10, "direction": "y"}},
                {"id": "side_slots_2", "op": "cut_slot", "params": {"plane": "top_face", "center": [-5, 40], "length": 80, "width": 10, "direction": "y"}},
            ],
            "outputs": {},
        }

        prompt = "\u521b\u5efa\u4e00\u4e2a120mm*80mm*15mm\u7684\u5b89\u88c5\u677f\uff0c\u5b89\u88c5\u677f\u6cbf\u5bbd\u5ea6\u65b9\u5411\u5206\u522b\u5728\u8ddd\u79bb\u4e24\u8fb95mm\u5904\u5f002\u4e2a\u5bbd\u5ea6\u4e3a10mm\u7684\u901a\u69fd"
        bound = bind_featureplan_semantics(prompt, plan)
        slot_1 = next(op for op in bound["operations"] if op["id"] == "side_slots")
        slot_2 = next(op for op in bound["operations"] if op["id"] == "side_slots_2")
        self.assertEqual(slot_1["params"]["center"], [-50.0, 0.0])
        self.assertEqual(slot_2["params"]["center"], [50.0, 0.0])

    def test_semantic_binding_repairs_malformed_provenance_paths(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        prompt = "Create a 120x80x12mm plate with a center boss."
        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "malformed_provenance",
            "metadata": {
                "inferred_parameters": [
                    # op-name + id joined by a dot => 4 segments, Policy rejects it
                    "create_base_plate.001.params.plane",
                    "create_center_boss.006.params.plane",
                    # references a param that will be removed / never existed
                    "cut_center_hole.007.params.depth",
                    "cut_center_hole.007.params.plane",
                ],
                "explicit_parameters": [],
            },
            "operations": [
                {"id": "001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 12, "plane": "Top"}},
                {"id": "006", "op": "create_center_boss", "params": {"diameter": 30, "height": 10, "plane": "top_face"}},
            ],
            "outputs": {},
        }

        bound = bind_featureplan_semantics(prompt, plan)
        inferred = bound["metadata"]["inferred_parameters"]
        # Malformed op-name+id paths are repaired to the real <id>.params.<param>.
        self.assertIn("001.params.plane", inferred)
        self.assertIn("006.params.plane", inferred)
        # Paths referencing non-existent operations/params are dropped.
        self.assertNotIn("cut_center_hole.007.params.depth", inferred)
        self.assertNotIn("cut_center_hole.007.params.plane", inferred)
        for path in inferred:
            parts = path.split(".")
            self.assertEqual(len(parts), 3)
            self.assertEqual(parts[1], "params")

    def test_semantic_binding_normalizes_invalid_host_to_base(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        prompt = "Create a 120x80x12mm plate and cut a slot on the top face."
        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "invalid_host",
            "operations": [
                {"id": "base_plate", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 12, "plane": "Top"}},
                # LLM emits an invalid host value that is not base/boss
                {"id": "slot_1", "op": "cut_slot", "params": {"plane": "top_face", "length": 40, "width": 10, "center": [0, 0], "host": "top_face"}},
            ],
            "outputs": {},
        }

        bound = bind_featureplan_semantics(prompt, plan)
        slot = next(op for op in bound["operations"] if op["id"] == "slot_1")
        self.assertIn(slot["params"]["host"], {"base", "boss"})

if __name__ == "__main__":
    unittest.main()












class TestSemanticBinding(unittest.TestCase):
    def test_semantic_binding_fills_m6_corner_hole_diameter(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "bind_case",
            "operations": [
                {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 12, "plane": "Top"}},
                {"id": "hole_001", "op": "cut_corner_holes", "params": {"edge_margin": 10}},
            ],
            "outputs": {},
        }

        bound = bind_featureplan_semantics("四角 M6 通孔 的安装板", plan)
        self.assertEqual(bound["operations"][1]["params"]["diameter"], 6.6)

    def test_semantic_binding_fills_explicit_corner_hole_diameter_from_prompt(self):
        from cad_dsl.semantic_binding import _infer_explicit_corner_hole_diameter_from_prompt

        self.assertEqual(_infer_explicit_corner_hole_diameter_from_prompt("四角做直径10mm通孔"), 10.0)
        self.assertEqual(_infer_explicit_corner_hole_diameter_from_prompt("四角开 6.5mm 孔"), 6.5)

    def test_semantic_binding_fills_m6_corner_hole_diameter_for_general_corner_hole_wording(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "bind_case",
            "operations": [
                {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 12, "plane": "Top"}},
                {"id": "hole_001", "op": "cut_corner_holes", "params": {"edge_margin": 10}},
            ],
            "outputs": {},
        }

        bound = bind_featureplan_semantics("四角留 M6 孔 的安装板", plan)
        self.assertEqual(bound["operations"][1]["params"]["diameter"], 6.6)
    def test_semantic_binding_drops_cut_center_hole_plane_and_center(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "bind_case",
            "operations": [
                {"id": "boss_001", "op": "create_center_boss", "params": {"diameter": 30, "height": 25}},
                {"id": "hole_001", "op": "cut_center_hole", "params": {"diameter": 10, "plane": "top_face", "center": [0, 0]}},
            ],
            "outputs": {},
        }

        bound = bind_featureplan_semantics("凸台中心开 10mm 通孔", plan)
        params = bound["operations"][1]["params"]
        self.assertNotIn("plane", params)
        self.assertNotIn("center", params)
        self.assertEqual(params["target"], "boss")

    def test_semantic_binding_normalizes_base_plate_plane_alias(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "bind_case",
            "operations": [
                {"id": "base_001", "op": "create_base_plate", "params": {"length": 100, "width": 60, "thickness": 10, "plane": "top_face"}},
            ],
            "outputs": {},
        }

        bound = bind_featureplan_semantics("长100宽60厚10的底板", plan)
        self.assertEqual(bound["operations"][0]["params"]["plane"], "Top")

    def test_semantic_binding_normalizes_extrude_boss_direction_alias(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "bind_case",
            "operations": [
                {"id": "extrude_001", "op": "extrude_boss", "params": {"sketch": "BaseSketch", "depth": 10, "direction": "normal"}},
            ],
            "outputs": {},
        }

        bound = bind_featureplan_semantics("拉伸一个底板", plan)
        self.assertEqual(bound["operations"][0]["params"]["direction"], "one_side")
    def test_semantic_binding_normalizes_left_right_side_slot_centers_from_edge_distance_prompt(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "slot_bind_case",
            "operations": [
                {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "cut_slot_on_left_side_001", "op": "cut_slot", "params": {"plane": "top_face", "center": [-100, 0], "length": 40, "width": 10, "through_all": True}},
                {"id": "cut_slot_on_right_side_001", "op": "cut_slot", "params": {"plane": "top_face", "center": [100, 0], "length": 40, "width": 10, "through_all": True}},
            ],
            "outputs": {},
        }

        prompt = "Cut two slots along the width direction from both side edges 20mm with slot width 10mm"
        bound = bind_featureplan_semantics(prompt, plan)
        self.assertEqual(bound["operations"][1]["params"]["direction"], "y")
        self.assertEqual(bound["operations"][2]["params"]["direction"], "y")
        self.assertEqual(bound["operations"][1]["params"]["center"], [-35.0, 0.0])
        self.assertEqual(bound["operations"][2]["params"]["center"], [35.0, 0.0])

    def test_semantic_binding_normalizes_generic_two_side_slot_ids_from_edge_distance_prompt(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "slot_bind_case",
            "operations": [
                {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "side_slots", "op": "cut_slot", "params": {"plane": "top_face", "center": [-100, 0], "length": 80, "width": 10, "through_all": True}},
                {"id": "side_slots_2", "op": "cut_slot", "params": {"plane": "top_face", "center": [100, 0], "length": 80, "width": 10, "through_all": True}},
            ],
            "outputs": {},
        }

        prompt = "\u5b89\u88c5\u677f\u6cbf\u5bbd\u5ea6\u65b9\u5411\u5206\u522b\u5728\u8ddd\u79bb\u4e24\u8fb920mm\u5904\u5f002\u4e2a\u5bbd\u5ea6\u4e3a10mm\u7684\u901a\u69fd"
        bound = bind_featureplan_semantics(prompt, plan)
        self.assertEqual(bound["operations"][1]["params"]["direction"], "y")
        self.assertEqual(bound["operations"][2]["params"]["direction"], "y")
        self.assertEqual(bound["operations"][1]["params"]["center"], [-35.0, 0.0])
        self.assertEqual(bound["operations"][2]["params"]["center"], [35.0, 0.0])

    def test_semantic_binding_normalizes_pocket_long_edge_direction_center_phrase(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "pocket_bind_case",
            "operations": [
                {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "pocket", "op": "cut_rectangle_pocket", "params": {"plane": "top_face", "center": [80, 0], "length": 10, "width": 10, "depth": 10}},
            ],
            "outputs": {},
        }

        prompt = "\u518d\u4ece\u5b89\u88c5\u677f\u4e0a\u8868\u9762\u7684\u957f\u8fb9\u65b9\u5411\u7684\u4e2d\u5fc3\u4f4d\u7f6e\u5207\u5272\u4e00\u4e2a10mm*10mm*10mm\u7684\u53e3\u888b"
        bound = bind_featureplan_semantics(prompt, plan)
        self.assertEqual(bound["operations"][1]["params"]["center"], [0.0, 35.0])

    def test_semantic_binding_swaps_reversed_slot_length_and_width(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "slot_bind_case",
            "operations": [
                {"id": "slot_001", "op": "cut_slot", "params": {"plane": "top_face", "center": [0, 0], "length": 10, "width": 40, "depth": 5}},
            ],
            "outputs": {},
        }

        bound = bind_featureplan_semantics("安装板上切一个10mm通槽", plan)
        params = bound["operations"][0]["params"]
        self.assertEqual(params["length"], 40)
        self.assertEqual(params["width"], 10)

    def test_semantic_binding_normalizes_generic_two_side_slot_ids_from_atomic_base_chain(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics
        from app.providers.local_provider import _policy_error_summary

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "slot_bind_case",
            "operations": [
                {"id": "new_001", "op": "create_new_part", "params": {}},
                {"id": "sketch_001", "op": "create_sketch", "params": {"name": "BaseSketch", "plane": "Top"}},
                {"id": "rect_001", "op": "sketch_center_rectangle", "params": {"sketch": "BaseSketch", "center": [0, 0], "length": 120, "width": 80}},
                {"id": "extrude_001", "op": "extrude_boss", "params": {"sketch": "BaseSketch", "depth": 15}},
                {"id": "side_slots", "op": "cut_slot", "params": {"plane": "top_face", "center": [0, 80], "length": 40, "width": 10, "through_all": True}},
                {"id": "side_slots_2", "op": "cut_slot", "params": {"plane": "top_face", "center": [0, -80], "length": 40, "width": 10, "through_all": True}},
            ],
            "outputs": {},
        }

        prompt = "\u5b89\u88c5\u677f\u6cbf\u5bbd\u5ea6\u65b9\u5411\u5206\u522b\u5728\u8ddd\u79bb\u4e24\u8fb920mm\u5904\u5f002\u4e2a\u5bbd\u5ea6\u4e3a10mm\u7684\u901a\u69fd"
        bound = bind_featureplan_semantics(prompt, plan)
        self.assertEqual(bound["operations"][4]["params"]["direction"], "y")
        self.assertEqual(bound["operations"][5]["params"]["direction"], "y")
        self.assertEqual(bound["operations"][4]["params"]["center"], [-35.0, 0.0])
        self.assertEqual(bound["operations"][5]["params"]["center"], [35.0, 0.0])
        self.assertEqual(_policy_error_summary(plan, prompt), "")

    def test_semantic_binding_defaults_top_face_for_top_cuts_and_holes(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "default_plane_case",
            "operations": [
                {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "hole_001", "op": "create_through_hole", "params": {"center": [0, 0], "diameter": 10}},
                {"id": "pocket_001", "op": "cut_rectangle_pocket", "params": {"center": [0, 0], "length": 10, "width": 10, "depth": 10}},
            ],
            "outputs": {},
        }

        bound = bind_featureplan_semantics("????????????", plan)
        self.assertEqual(bound["operations"][1]["params"]["plane"], "top_face")
        self.assertEqual(bound["operations"][2]["params"]["plane"], "top_face")

    def test_semantic_binding_infers_unique_pattern_seed_feature(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "pattern_seed_case",
            "operations": [
                {"id": "base_001", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 12, "plane": "Top"}},
                {"id": "hole_001", "op": "create_through_hole", "params": {"center": [-40, 0], "diameter": 6}},
                {"id": "pattern_001", "op": "create_linear_pattern", "params": {"direction": "x", "count": 4, "spacing": 20}},
            ],
            "outputs": {},
        }

        bound = bind_featureplan_semantics("???????????? 4 ?", plan)
        self.assertEqual(bound["operations"][2]["params"]["seed_feature"], "hole_001")

    def test_semantic_binding_maps_outer_fillet_target(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "bind_case",
            "operations": [
                {"id": "fillet_001", "op": "add_fillet", "params": {"radius": 3, "target": "perimeter", "center": [0, 0]}},
            ],
            "outputs": {},
        }

        bound = bind_featureplan_semantics("四周加 R3 圆角", plan)
        params = bound["operations"][0]["params"]
        self.assertEqual(params["target"], "outer_edges")
        self.assertNotIn("center", params)









class TestSemanticBindingRegressionForWorkbenchPrompts(unittest.TestCase):
    def test_semantic_completeness_detects_missing_corner_holes_for_corner_hole_prompt(self):
        issues = local_provider._semantic_completeness_issues(
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "demo",
                "operations": [
                    {"id": "base_plate", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                    {"id": "boss_001", "op": "create_center_boss", "params": {"diameter": 20, "height": 15}},
                ],
                "outputs": {},
            },
            "Create a 120x80x15mm installation plate with 10mm corner through holes and a 20mm center boss.",
        )

        self.assertIn("missing requested cut_corner_holes operation", issues)

    def test_semantic_completeness_detects_missing_corner_holes_for_four_corner_through_hole_prompt(self):
        issues = local_provider._semantic_completeness_issues(
            {
                "version": "2.0",
                "unit": "mm",
                "document_type": "part",
                "part_name": "demo",
                "operations": [
                    {"id": "base_plate", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                    {"id": "boss_001", "op": "create_center_boss", "params": {"diameter": 20, "height": 15}},
                ],
                "outputs": {},
            },
            "\u56db\u89d2\u505a\u76f4\u5f8410mm\u7684\u901a\u5b54\uff0c\u4e2d\u95f4\u52a0\u4e00\u4e2a\u76f4\u5f8420mm\u7684\u51f8\u53f0\u3002",
        )

        self.assertIn("missing requested cut_corner_holes operation", issues)

    def test_semantic_binding_infers_full_slot_span_for_generic_through_slot_prompt(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "slot_span_case",
            "operations": [
                {"id": "base_plate", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "side_slots", "op": "cut_slot", "params": {"plane": "top_face", "center": [-100, 0], "length": 30, "width": 10, "direction": "y"}},
                {"id": "side_slots_2", "op": "cut_slot", "params": {"plane": "top_face", "center": [100, 0], "length": 30, "width": 10, "direction": "y"}},
            ],
            "outputs": {},
        }

        prompt = "Create two through slots along the width direction, 25mm from both side edges, slot width 10mm"
        bound = bind_featureplan_semantics(prompt, plan)
        slot_1 = next(op for op in bound["operations"] if op["id"] == "side_slots")
        slot_2 = next(op for op in bound["operations"] if op["id"] == "side_slots_2")

        self.assertEqual(slot_1["params"]["direction"], "y")
        self.assertEqual(slot_2["params"]["direction"], "y")
        self.assertEqual(slot_1["params"]["length"], 80)
        self.assertEqual(slot_2["params"]["length"], 80)
        self.assertNotIn("through_all", slot_1["params"])
        self.assertNotIn("through_all", slot_2["params"])

    def test_semantic_binding_expands_two_short_edge_pockets(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "pocket_pair_case",
            "operations": [
                {"id": "base_plate", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "pocket", "op": "cut_rectangle_pocket", "params": {"plane": "top_face", "center": [0, 0], "length": 8, "width": 8, "depth": 8}},
            ],
            "outputs": {},
        }

        prompt = "\u4ece\u4e0a\u8868\u9762\u7684\u77ed\u8fb9\u4e2d\u5fc3\u4f4d\u7f6e\u3001\u8ddd\u79bb\u8fb90mm\u5207\u5272\u4e00\u4e2a8mm*8mm*8mm\u7684\u53e3\u888b\uff0c\u4e24\u4fa7\u5404\u4e00\u4e2a\u3002"
        bound = bind_featureplan_semantics(prompt, plan)
        pockets = [op for op in bound["operations"] if op["op"] == "cut_rectangle_pocket"]

        self.assertEqual(len(pockets), 2)
        self.assertEqual(pockets[0]["params"]["center"], [-56.0, 0.0])
        self.assertEqual(pockets[1]["params"]["center"], [56.0, 0.0])

    def test_semantic_binding_marks_center_hole_as_through_all_for_boss_and_base_request(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "boss_hole_case",
            "operations": [
                {"id": "base_plate", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "center_boss", "op": "create_center_boss", "params": {"diameter": 20, "height": 15}},
                {"id": "boss_hole", "op": "cut_center_hole", "params": {"diameter": 10}},
            ],
            "outputs": {},
        }

        prompt = "Create a 120x80x15mm installation plate with a 20mm center boss and a 10mm through hole through the boss and base"
        bound = bind_featureplan_semantics(prompt, plan)
        hole = next(op for op in bound["operations"] if op["id"] == "boss_hole")

        self.assertEqual(hole["params"]["target"], "boss")
        self.assertTrue(hole["params"]["through_all"])
        self.assertNotIn("plane", hole["params"])
        self.assertNotIn("center", hole["params"])


class TestSlotDepthSemanticBinding(unittest.TestCase):
    def test_semantic_binding_does_not_force_through_all_for_generic_slot_request(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "slot_case",
            "operations": [
                {"id": "base_plate", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "side_slots", "op": "cut_slot", "params": {"plane": "top_face", "center": [0, 0], "length": 20, "width": 10, "direction": "y"}},
            ],
            "outputs": {},
        }

        prompt = "鐎瑰顥婇弶鎸庨儴鐎硅棄瀹抽弬鐟版倻瀵偓娑撯偓娑擃亜顔旀惔?0mm閻ㄥ嫰鈧碍蝎"
        bound = bind_featureplan_semantics(prompt, plan)
        params = bound["operations"][1]["params"]
        self.assertNotIn("through_all", params)
class TestSlotDepthCompletion(unittest.TestCase):
    def test_semantic_binding_infers_default_slot_depth_when_missing(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "slot_depth_case",
            "operations": [
                {"id": "base_plate", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "slot_001", "op": "cut_slot", "params": {"plane": "top_face", "center": [0, 0], "length": 40, "width": 10, "direction": "y"}},
            ],
            "outputs": {},
        }

        bound = bind_featureplan_semantics("沿宽度方向开一个宽度10mm的通槽", plan)
        params = bound["operations"][1]["params"]
        self.assertEqual(params["depth"], 7.5)
        self.assertNotIn("through_all", params)


class TestCornerHoleCompletion(unittest.TestCase):
    def test_semantic_binding_repairs_invalid_corner_hole_edge_margin(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "corner_hole_invalid_margin_case",
            "operations": [
                {"id": "base_plate", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "corner_holes", "op": "cut_corner_holes", "params": {"diameter": 10, "edge_margin": 2.5}},
            ],
            "outputs": {},
        }

        bound = bind_featureplan_semantics("创建一个120x80x15安装板，四角10mm通孔", plan)
        params = bound["operations"][1]["params"]
        self.assertEqual(params["edge_margin"], 15.0)

    def test_semantic_binding_infers_default_corner_hole_edge_margin_when_missing(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "corner_hole_case",
            "operations": [
                {"id": "base_plate", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "corner_holes", "op": "cut_corner_holes", "params": {"diameter": 10}},
            ],
            "outputs": {},
        }

        bound = bind_featureplan_semantics("?????10mm???", plan)
        params = bound["operations"][1]["params"]
        self.assertEqual(params["edge_margin"], 15.0)





class TestExplicitPromptBindingStability(unittest.TestCase):
    def test_semantic_binding_rebinds_explicit_prompt_dimensions_without_drifting_other_features(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "stability_case",
            "operations": [
                {"id": "base_plate", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "center_boss", "op": "create_center_boss", "params": {"diameter": 30, "height": 15}},
                {"id": "center_through_hole", "op": "cut_center_hole", "params": {"diameter": 20, "target": "boss", "through_all": True}},
                {"id": "side_slots_001", "op": "cut_slot", "params": {"plane": "top_face", "center": [-50, -16], "length": 15, "width": 8, "depth": 7.5}},
                {"id": "side_slots_002", "op": "cut_slot", "params": {"plane": "top_face", "center": [50, 16], "length": 15, "width": 8, "depth": 7.5}},
                {"id": "side_pockets_001", "op": "cut_rectangle_pocket", "params": {"plane": "top_face", "center": [0, -35], "length": 10, "width": 10, "depth": 10}},
                {"id": "side_pockets_002", "op": "cut_rectangle_pocket", "params": {"plane": "top_face", "center": [0, 35], "length": 10, "width": 10, "depth": 10}},
            ],
            "outputs": {},
        }

        prompt_a = "创建一个120mm*80mm*15mm的安装板，四角做直径10mm的通孔四周边距10mm，安装板上表面加直径为20mm中心凸台，中心开直径10mm的通孔。沿着安装板上表面的宽度方向分别在距离两边20mm处开2个宽度为8mm的通槽。再从上表面的长边中心、边距0mm切割一个10mm*10mm*10mm的口袋，两侧各一个。安装板加R3圆角。"
        prompt_b = "创建一个120mm*80mm*15mm的安装板，四角做直径10mm的通孔四周边距10mm，安装板上表面加直径为30mm中心凸台，中心开直径10mm的通孔。沿着安装板上表面的宽度方向分别在距离两边20mm处开2个宽度为8mm的通槽。再从上表面的长边中心、边距0mm切割一个10mm*10mm*10mm的口袋，两侧各一个。安装板加R3圆角。"

        bound_a = bind_featureplan_semantics(prompt_a, plan)
        bound_b = bind_featureplan_semantics(prompt_b, plan)

        ops_a = {op["id"]: op for op in bound_a["operations"]}
        ops_b = {op["id"]: op for op in bound_b["operations"]}

        self.assertEqual(ops_a["center_boss"]["params"]["diameter"], 20)
        self.assertEqual(ops_b["center_boss"]["params"]["diameter"], 30)
        self.assertEqual(ops_a["center_through_hole"]["params"]["diameter"], 10)
        self.assertEqual(ops_b["center_through_hole"]["params"]["diameter"], 10)
        self.assertEqual(ops_a["side_slots_001"]["params"]["direction"], "y")
        self.assertEqual(ops_b["side_slots_001"]["params"]["direction"], "y")
        self.assertEqual(ops_a["side_slots_001"]["params"]["length"], 80)
        self.assertEqual(ops_b["side_slots_001"]["params"]["length"], 80)
        self.assertEqual(ops_a["side_slots_001"]["params"]["width"], 8)
        self.assertEqual(ops_b["side_slots_001"]["params"]["width"], 8)
        self.assertEqual(ops_a["side_slots_001"]["params"]["center"], ops_b["side_slots_001"]["params"]["center"])
        self.assertEqual(ops_a["side_slots_002"]["params"]["center"], ops_b["side_slots_002"]["params"]["center"])
        self.assertEqual(ops_a["side_pockets_001"]["params"], ops_b["side_pockets_001"]["params"])
        self.assertEqual(ops_a["side_pockets_002"]["params"], ops_b["side_pockets_002"]["params"])

class TestSemanticHostBinding(unittest.TestCase):
    def test_semantic_binding_marks_base_top_face_features_with_base_host(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "host_binding_base_case",
            "operations": [
                {"id": "base_plate", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "center_boss", "op": "create_center_boss", "params": {"diameter": 20, "height": 15}},
                {"id": "slot_001", "op": "cut_slot", "params": {"plane": "top_face", "center": [0, 0], "length": 40, "width": 8, "depth": 7.5}},
                {"id": "pocket_001", "op": "cut_rectangle_pocket", "params": {"plane": "top_face", "center": [0, 0], "length": 10, "width": 10, "depth": 10}},
            ],
            "outputs": {},
        }

        prompt = "安装板上表面加直径20mm中心凸台。沿着安装板上表面的宽度方向开一个宽度8mm的通槽，再从安装板上表面切一个10mm*10mm*10mm的口袋。"
        bound = bind_featureplan_semantics(prompt, plan)
        ops = {op["id"]: op for op in bound["operations"]}

        self.assertEqual(ops["center_boss"]["params"]["host"], "base")
        self.assertEqual(ops["slot_001"]["params"]["host"], "base")
        self.assertEqual(ops["pocket_001"]["params"]["host"], "base")

    def test_semantic_binding_marks_boss_top_face_pocket_with_boss_host(self):
        from cad_dsl.semantic_binding import bind_featureplan_semantics

        plan = {
            "version": "2.0",
            "unit": "mm",
            "document_type": "part",
            "part_name": "host_binding_boss_case",
            "operations": [
                {"id": "base_plate", "op": "create_base_plate", "params": {"length": 120, "width": 80, "thickness": 15, "plane": "Top"}},
                {"id": "center_boss", "op": "create_center_boss", "params": {"diameter": 20, "height": 15}},
                {"id": "pocket_001", "op": "cut_rectangle_pocket", "params": {"plane": "top_face", "center": [0, 0], "length": 8, "width": 8, "depth": 8}},
            ],
            "outputs": {},
        }

        prompt = "从凸台上表面的中心位置切割一个8mm*8mm*8mm的口袋。"
        bound = bind_featureplan_semantics(prompt, plan)
        pocket = next(op for op in bound["operations"] if op["id"] == "pocket_001")

        self.assertEqual(pocket["params"]["host"], "boss")
