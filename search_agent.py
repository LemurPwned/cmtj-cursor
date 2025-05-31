from typing import Any, list

import yaml
from loguru import logger
from pocketflow import BatchNode, Flow, Node

from index.llama_builder import SEARCH_ENGINE
from utils.call_llm import call_llm


class GenerateSubQueries(Node):
    """Node that takes a user query and generates additional sub-queries for comprehensive search"""

    def prep(self, shared: dict[str, Any]) -> str:
        if user_query := shared.get("user_query"):
            return user_query
        raise ValueError("No user query found in shared store")

    def exec(self, user_query: str) -> dict:
        prompt = f"""
Given the user question: "{user_query}"

Generate 2-3 specific sub-queries that would help provide a comprehensive answer.
These sub-queries should explore different aspects, contexts, or related information.
If the user query contains an acronym, make sure you ask for the meaning of the acronym.

Output in YAML format:
```yaml
main_query: "{user_query}"
sub_queries:
  - "sub-query 1"
  - "sub-query 2"
  - "sub-query 3"
```
"""
        response = call_llm(prompt)
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

    def prep(self, shared: dict[str, Any]) -> list[str]:
        # Return all queries for batch processing
        return shared["all_queries"]

    def exec(self, query: str) -> dict:
        # This would use your llamaindex search engine
        # Placeholder for actual llamaindex search implementation
        try:
            # Replace with actual llamaindex search call
            search_results = SEARCH_ENGINE.query(query)
            # For now, simulating search results
            logger.warning(f"Search results for query: {query}: {search_results}")
            return {"query": query, "results": search_results, "success": True}
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
        search_results = shared["search_results"]
        query_breakdown = shared["query_breakdown"]

        return user_query, search_results, query_breakdown

    def exec(self, prep_data: tuple) -> str:
        user_query, search_results, query_breakdown = prep_data

        # Prepare context from all search results
        context_parts = []
        context_parts.extend(
            f"Query: {result['query']}\nResults: {result['results']}\n"
            for result in search_results
            if result["success"]
        )
        combined_context = "\n".join(context_parts)

        prompt = f"""
Based on the search results below, provide a comprehensive answer to the user's question.
If the user's question is not related to the search results, say "I don't know".
If there is no information in the search results, say "I don't know".

Make sure to cite the source of the information in the answer, never answer from your own knowledge.
ONLY USE THE INFORMATION FROM THE SEARCH RESULTS TO ANSWER THE QUESTION. DO NOT INFER ANY OTHER INFORMATION.

User Question: {user_query}

Search Results from multiple queries:
{combined_context}

Instructions:
1. Synthesize information from all search results
2. Provide a clear, well-structured answer
3. If there are conflicting information, mention it
4. Cite which sub-queries contributed to different parts of your answer when relevant

Final Answer:
"""

        return call_llm(prompt)

    def post(self, shared: dict[str, Any], prep_res: tuple, exec_res: str) -> str:
        shared["final_answer"] = exec_res
        logger.info("Final answer generated and stored")
        return "default"


def qa_agent():
    """Create and return the QA agent flow"""

    # Create nodes
    generate_queries = GenerateSubQueries()
    batch_search = BatchSearchDocuments()
    synthesize_answer = SynthesizeFinalAnswer()

    # Connect nodes in sequence
    generate_queries >> batch_search >> synthesize_answer

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
        "final_answer": shared.get("final_answer", ""),
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
