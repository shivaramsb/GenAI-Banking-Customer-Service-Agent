"""
Comprehensive Test Cases: Structured vs ChatGPT Mode Comparison

Tests accuracy, completeness, and conversational quality across different query types.
"""

import logging
import sys
sys.path.append('.')

from src.agent_core import process_query

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Test cases organized by category
TEST_CASES = {
    "Accuracy-Critical Queries": [
        {
            "query": "how many hdfc credit cards",
            "expected": "Exact count: 19",
            "critical": "Count must be 100% accurate"
        },
        {
            "query": "list all hdfc credit cards",
            "expected": "All 19 cards listed by name",
            "critical": "Must list ALL cards, no truncation"
        },
        {
            "query": "explain all sbi loans",
            "expected": "Complete details for every SBI loan",
            "critical": "Must show ALL loans with full details"
        }
    ],
    
    "General Questions": [
        {
            "query": "what is a credit card",
            "expected": "Clear explanation of credit cards",
            "critical": "Natural, easy to understand"
        },
        {
            "query": "tell me about hdfc",
            "expected": "Overview of HDFC bank and products",
            "critical": "Conversational, not robotic"
        }
    ],
    
    "Recommendations": [
        {
            "query": "best credit card for students",
            "expected": "Recommended cards with reasoning",
            "critical": "Should analyze and explain why"
        },
        {
            "query": "which loan is better for home buyers",
            "expected": "Home loan recommendations",
            "critical": "Should understand context and suggest appropriately"
        }
    ],
    
    "Comparisons": [
        {
            "query": "compare hdfc millennia vs hdfc regalia gold",
            "expected": "Side-by-side comparison table",
            "critical": "Clear comparison format"
        },
        {
            "query": "difference between sbi and hdfc credit cards",
            "expected": "Comparison of offerings",
            "critical": "Should handle cross-bank comparison"
        }
    ],
    
    "Multi-turn Conversation": [
        {
            "conversation": [
                "tell me about hdfc credit cards",
                "which one has the lowest fees",
                "explain the benefits of that card",
                "is it good for students"
            ],
            "expected": "Each response uses context from previous messages",
            "critical": "Full conversation context maintained"
        }
    ]
}

def run_test(query, mode, chat_history=None):
    """Run a single test query"""
    try:
        response = process_query(query, mode=mode, chat_history=chat_history)
        return {
            "success": True,
            "text": response.get('text', ''),
            "source": response.get('source', ''),
            "data_count": len(response.get('data', [])) if response.get('data') else 0
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def main():
    print("=" * 100)
    print("COMPREHENSIVE MODE COMPARISON TEST")
    print("=" * 100)
    
    results = {
        "structured": {"pass": 0, "fail": 0, "details": []},
        "chatgpt": {"pass": 0, "fail": 0, "details": []}
    }
    
    # Test each category
    for category, tests in TEST_CASES.items():
        if category == "Multi-turn Conversation":
            continue  # Handle separately
            
        print(f"\n{'='*100}")
        print(f"CATEGORY: {category}")
        print(f"{'='*100}\n")
        
        for i, test in enumerate(tests, 1):
            query = test['query']
            print(f"\n{i}. Query: \"{query}\"")
            print(f"   Expected: {test['expected']}")
            print(f"   Critical: {test['critical']}\n")
            
            # Test Structured Mode
            print("   🔷 STRUCTURED MODE:")
            struct_result = run_test(query, mode="structured")
            if struct_result['success']:
                print(f"      Source: {struct_result['source']}")
                print(f"      Data items: {struct_result['data_count']}")
                print(f"      Response: {struct_result['text'][:150]}...")
                results["structured"]["details"].append({
                    "query": query,
                    "result": struct_result
                })
            else:
                print(f"      ❌ ERROR: {struct_result['error']}")
                results["structured"]["fail"] += 1
            
            # Test ChatGPT Mode
            print("\n   💬 CHATGPT MODE:")
            chatgpt_result = run_test(query, mode="chatgpt")
            if chatgpt_result['success']:
                print(f"      Source: {chatgpt_result['source']}")
                print(f"      Data items: {chatgpt_result['data_count']}")
                print(f"      Response: {chatgpt_result['text'][:150]}...")
                results["chatgpt"]["details"].append({
                    "query": query,
                    "result": chatgpt_result
                })
            else:
                print(f"      ❌ ERROR: {chatgpt_result['error']}")
                results["chatgpt"]["fail"] += 1
    
    # Test multi-turn conversation
    print(f"\n{'='*100}")
    print(f"CATEGORY: Multi-turn Conversation")
    print(f"{'='*100}\n")
    
    conversation = TEST_CASES["Multi-turn Conversation"][0]["conversation"]
    history = []
    
    print("Testing ChatGPT mode with conversation context:\n")
    for i, query in enumerate(conversation, 1):
        print(f"{i}. User: \"{query}\"")
        result = run_test(query, mode="chatgpt", chat_history=history)
        
        if result['success']:
            print(f"   Bot: {result['text'][:200]}...\n")
            
            # Update history
            history.append({"role": "user", "content": query})
            history.append({"role": "assistant", "content": result['text']})
        else:
            print(f"   ❌ ERROR: {result['error']}\n")
    
    # Summary
    print(f"\n{'='*100}")
    print("TEST SUMMARY")
    print(f"{'='*100}\n")
    print(f"Structured Mode: {results['structured']['pass']} pass, {results['structured']['fail']} fail")
    print(f"ChatGPT Mode: {results['chatgpt']['pass']} pass, {results['chatgpt']['fail']} fail")
    print("\n" + "="*100)

if __name__ == "__main__":
    main()
