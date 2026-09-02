import litellm
import traceback

def test_exc():
    try:
        err = litellm.llms.vertex_ai.common_utils.VertexAIError(status_code=429, message="Quota Exceeded")
        raise litellm.exceptions.BadRequestError("429 Too Many Requests", err, model="gemini-3.6-flash")
    except Exception as e:
        print(type(e))
        print("dir:", dir(e))
        print("status_code:", getattr(e, "status_code", None))
        print("message:", getattr(e, "message", None))
        print("llm_provider:", getattr(e, "llm_provider", None))

test_exc()
