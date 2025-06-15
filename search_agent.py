from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any

import yaml
from duckduckgo_search import DDGS
from loguru import logger
from pocketflow import BatchNode, Flow, Node

from index.llama_builder import RETRIEVER
from utils.call_llm import call_llm


class GenerateSubQueries(Node):
    """Node that takes a user query and generates additional sub-queries for comprehensive search"""

    def prep(self, shared: dict[str, Any]) -> str:
        if user_query := shared.get("user_query"):
            return {
                "user_query": user_query,
                "model": shared.get("model", "o4-mini"),
            }
        raise ValueError("No user query found in shared store")

    def exec(self, params: dict[str, Any]) -> dict:
        user_query = params["user_query"]
        model = params["model"]
        prompt = f"""
Given the user question: "{user_query}"

Generate 2-3 specific sub-queries that would help provide a comprehensive answer.
These sub-queries should explore different aspects, contexts, or related information.
If the user query contains an acronym, make sure you ask for the meaning of the acronym.
The context of the question is always either CMTJ library, spintronics, or magnetic physics and materials.
Remember, the generated subqueries are to be used for searching the document search engine, and the web search engine,
so they are not to be directed to the user.
Output in YAML format:
```yaml
main_query: "{user_query}"
sub_queries:
  - "sub-query 1"
  - "sub-query 2"
  - "sub-query 3"
```
"""
        response = call_llm(prompt, model=model)
        yaml_str = response.split("```yaml")[1].split("```")[0].strip()
        result = yaml.safe_load(yaml_str)

        # Validate structure
        assert "main_query" in result
        assert "sub_queries" in result
        assert isinstance(result["sub_queries"], list)

        return result

    def post(self, shared: dict[str, Any], prep_res: str, exec_res: dict) -> str:
        # Store all queries (main + sub) for batch processing
        all_queries = [exec_res["main_query"]] + exec_res["sub_queries"]
        shared["all_queries"] = all_queries
        shared["query_breakdown"] = exec_res
        logger.info(f"Generated {len(exec_res['sub_queries'])} sub-queries")
        for query in exec_res["sub_queries"]:
            logger.info(f"Sub-query: {query}")
        return "default"


class BatchSearchDocuments(BatchNode):
    """BatchNode that searches documents for each query using llamaindex"""

    TOPK = 5

    def prep(self, shared: dict[str, Any]) -> list[str]:
        # Return all queries for batch processing
        return shared["all_queries"]

    def exec(self, query: str) -> dict:
        # This would use your llamaindex search engine
        # Placeholder for actual llamaindex search implementation
        try:
            # Replace with actual llamaindex search call
            search_results = RETRIEVER.retrieve(query)
            search_results = [r for r in search_results if r.score > 0.5][: BatchSearchDocuments.TOPK]
            res_content = "Here are the search results:\n"
            for i, r in enumerate(search_results):
                txt = r.text.replace("\n", " ")
                mtdata = (
                    f"Source [{r.metadata.get('file_name', 'unknown')}]".replace(".md", "")
                    .replace(".txt", "")
                    .replace(".pdf", "")
                )
                res_content += f"Context fragment {i + 1}:\n{txt}\n{mtdata}\n\n"
            # For now, simulating search results
            logger.warning(f"Search results for query: {query}: {res_content}")
            return {"query": query, "results": res_content, "success": True}
        except Exception as e:
            return {
                "query": query,
                "results": f"Search failed: {str(e)}",
                "success": False,
            }

    def post(self, shared: dict[str, Any], prep_res: list[str], exec_res_list: list[dict]) -> str:
        # Store all search results
        shared["search_results"] = exec_res_list

        successful_searches = len([r for r in exec_res_list if r["success"]])
        logger.info(f"Completed {successful_searches}/{len(exec_res_list)} searches successfully")

        return "default"


class SynthesizeFinalAnswer(Node):
    """Node that combines all search results to produce a comprehensive final answer"""

    def prep(self, shared: dict[str, Any]) -> tuple:
        user_query = shared["user_query"]
        search_results = shared.get("search_results", [])
        query_breakdown = shared["query_breakdown"]
        web_search_results = shared.get("web_search_results", [])
        model = shared.get("model", "o4-mini")
        return {
            "user_query": user_query,
            "search_results": search_results,
            "query_breakdown": query_breakdown,
            "web_search_results": web_search_results,
            "model": model,
        }

    def exec(self, params: dict[str, Any]) -> str:
        user_query = params["user_query"]
        search_results = params["search_results"]
        # query_breakdown = params["query_breakdown"]
        web_search_results = params["web_search_results"]
        model = params["model"]

        # Prepare context from all search results
        context_parts = []
        context_parts.extend(
            f"Query: {result['query']}\nResults: {result['results']}\n"
            for result in search_results
            if result["success"]
        )
        combined_context = "\n".join(context_parts)
        logger.debug(web_search_results)
        web_search_results = list(set(web_search_results))
        if len(web_search_results) == 1 and "No web search results found." in web_search_results[0]:
            web_context = web_search_results[0]
        else:
            web_context = "\n".join(
                f"Web Search Result {i + 1}:\n{result['title']}\n{result['snippet']}\n{result['url']}\n"
                for i, result in enumerate(web_search_results)
            )

        prompt = f"""
Based on the search results below, provide a comprehensive answer to the user's question.
If the user's question is not related to the search results, say "I don't know".
If there is no information in the search results, say "I don't know".

Make sure to cite the source of the information in the answer, never answer from your own knowledge.
ONLY USE THE INFORMATION FROM THE SEARCH RESULTS TO ANSWER THE QUESTION. DO NOT INFER ANY OTHER INFORMATION.

User Question: {user_query}

Search Results from document search:
{combined_context}

Search Results from web search:
{web_context}

Instructions:
1. Synthesize information from all search results (both document search and web search)
2. Provide a clear, well-structured answer
3. If there are conflicting information, mention it
4. Cite which sub-queries contributed to different parts of your answer when relevant
5. When giving the final answer, make sure to pass the exact source of the information
    in the form it has been provided to you
6. Distinguish between information from document search vs web search when citing sources
7. Prefer information from the document search over the web search
Final Answer:
"""
        logger.debug(prompt)
        return call_llm(prompt, model=model)

    def post(self, shared: dict[str, Any], prep_res: tuple, exec_res: str) -> str:
        shared["response"] = exec_res
        logger.info("Final answer generated and stored")
        return exec_res


class WebSearch(BatchNode):
    """Node that searches the web for information"""

    def prep(self, shared: dict[str, Any]) -> str:
        return shared["user_query"]

    def exec(self, user_query: str) -> str:
        def search_with_timeout():
            return DDGS().text(
                user_query,
                region="en-us",
                safesearch="off",
                max_results=5,
            )

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(search_with_timeout)
                results = future.result(timeout=3)

            # Format results for LLM processing
            web_context = "Web search results:\n"
            for i, result in enumerate(results, 1):
                web_context += f"{i}. {result['title']}\n"
                web_context += f"   {result['body']}\n"
                web_context += f"   URL: {result['href']}\n\n"
            return web_context if results else "No web search results found."

        except FutureTimeoutError:
            logger.warning("Web search timed out after 15 seconds")
            return "No web search results found."
        except Exception as e:
            logger.error(f"Web search failed: {str(e)}")
            return "No web search results found."

    def post(self, shared: dict[str, Any], prep_res: str, exec_res: str) -> str:
        shared["web_search_results"] = exec_res
        logger.info("Web search results stored")
        return "default"


def qa_agent(allow_web_search: bool = True):
    """Create and return the QA agent flow"""

    # Create nodes
    generate_queries = GenerateSubQueries()
    batch_search = BatchSearchDocuments()
    web_search = WebSearch()
    synthesize_answer = SynthesizeFinalAnswer()

    # Connect nodes in sequence
    # Both batch_search and web_search run after generate_queries
    generate_queries >> batch_search
    batch_search >> synthesize_answer
    if allow_web_search:
        generate_queries >> web_search
        web_search >> synthesize_answer

    # Create flow
    return Flow(start=generate_queries)


def run_qa_agent(user_query: str):
    """Convenience function to run the QA agent with a user query"""

    # Initialize shared store
    shared = {"user_query": user_query}

    # Create and run the agent
    agent = qa_agent()
    agent.run(shared)

    # Return results
    return {
        "user_query": user_query,
        "sub_queries": shared.get("query_breakdown", {}).get("sub_queries", []),
        "search_results": shared.get("search_results", []),
        "web_search_results": shared.get("web_search_results", []),
        "final_answer": shared.get("response", ""),
    }


# Example usage
if __name__ == "__main__":
    # Test the QA agent
    result = run_qa_agent("What is PIMM simulation?")

    logger.info("=" * 50)
    logger.info("QA AGENT RESULTS")
    logger.info("=" * 50)
    logger.info(f"Original Query: {result['user_query']}")
    logger.info("\nGenerated Sub-queries:")
    for i, sq in enumerate(result["sub_queries"], 1):
        logger.info(f"  {i}. {sq}")

    logger.info("\nFinal Answer:")
    logger.info(result["final_answer"])
