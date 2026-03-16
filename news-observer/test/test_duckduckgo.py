from fact_checker import FactChecker

def main():
    # 这里的 api_base / model 随便填一个字符串即可，暂时不用 LLM
    checker = FactChecker(
        api_base="http://localhost:11434/v1",
        model="dummy-model",
        temperature=0.0,
        max_tokens=10,
        search_engine="duckduckgo",
        searxng_url=None,
        search_config={
            # 如果没有代理，把 proxy 去掉或设为 None
            # "proxy": "socks5://127.0.0.1:20170",
            "timeout": 30,
        },
    )

    query = "北京 天气"
    results = checker._search_with_duckduckgo(query, num_results=5)
    print(f"共返回 {len(results)} 条结果")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['title']}  ->  {r['url']}")

if __name__ == "__main__":
    main()