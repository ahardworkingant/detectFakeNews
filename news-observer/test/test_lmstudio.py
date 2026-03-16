from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio",  # LM Studio 默认随便填非空即可
)

resp = client.chat.completions.create(
    model="qwen/qwen3-8b",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "用一句话介绍一下你自己。"},
    ],
    temperature=0,
    max_tokens=100,
)

print(resp.choices[0].message.content)