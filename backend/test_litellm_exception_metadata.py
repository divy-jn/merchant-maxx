import os
import json
from litellm import completion
from litellm.exceptions import BadRequestError

# We will intentionally trigger a Gemini 400 by passing a history ending with an AIMessage.
def test_400():
    try:
        completion(
            model="gemini/gemini-3.6-flash",
            messages=[
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"}
            ]
        )
    except Exception as e:
        print("--- 400 ERROR ---")
        print(f"Type: {type(e)}")
        print(f"Status Code: {getattr(e, 'status_code', None)}")
        print(f"Message: {getattr(e, 'message', None)}")
        print(f"Response Object: {getattr(e, 'response', None)}")

# For a 429, we would need to mock or spam it. 
# But we can look at the 400 error first to see what properties it has.
if __name__ == "__main__":
    os.environ["GEMINI_API_KEY"] = os.environ.get("LLM_API_KEY")
    test_400()
