# Test Query Suite - 50 Questions

Comprehensive test cases covering all intent types, edge cases, and multi-turn scenarios for the Banking Assistant.

---

## 1. COUNT Queries (10 queries)

### Basic COUNT
1. "how many SBI credit cards"
2. "how many HDFC debit cards"
3. "count SBI loans"
4. "total number of Axis credit cards"

### COUNT with Category
5. "how many home loans are available"
6. "count all credit cards"
7. "total debit cards from all banks"

### COUNT Edge Cases
8. "how many cards" (should CLARIFY - no bank)
9. "SBI credit cards count" (different phrasing)
10. "tell me the number of HDFC loans"

---

## 2. LIST Queries (8 queries)

### Basic LIST
11. "list all SBI credit cards"
12. "show me HDFC debit cards"
13. "display all Axis loans"

### LIST with Variations
14. "what are the SBI credit cards"
15. "show all home loans"
16. "give me all SBI products"

### LIST Edge Cases
17. "list cards" (should CLARIFY - no bank/category)
18. "SBI" (vague - should CLARIFY)
how many cards
---

## 3. FAQ Queries (12 queries)

### Application Process
19. "how to apply for loan"
20. "how to apply for SBI credit card"
21. "application process for HDFC home loan"

### Requirements/Documents
22. "what documents are needed for loan"
23. "documents required for credit card application"
24. "eligibility criteria for home loan"

### Procedures/Steps
25. "how many steps to apply for loan" (FAQ, NOT COUNT!)
26. "what is the process to open SBI account"
27. "how to close credit card"

### Fees/Charges
28. "how much fees for SBI credit card"
29. "what are the charges for loan"

### General Banking
30. "how many times can I withdraw" (FAQ, NOT COUNT!)

---

## 4. COMPARE Queries (6 queries)

### Two Banks
31. "compare SBI vs HDFC home loan"
32. "SBI credit card versus Axis credit card"
33. "difference between SBI and HDFC debit cards"

### Specific Products
34. "compare SBI Prime and HDFC Regalia"
35. "SBI home loan vs HDFC home loan interest rates"

### Multiple Products
36. "compare all home loans"

---

## 5. RECOMMEND Queries (5 queries)

### User Preference
37. "best credit card for students"
38. "recommend a good home loan"
39. "which is the best SBI credit card"

### Use Case Based
40. "suitable credit card for travel"
41. "best loan for small business"

---

## 6. EXPLAIN Queries (4 queries)

### Single Product
42. "explain SBI SimplySave credit card"
43. "tell me about HDFC MoneyBack"
44. "details of SBI home loan"

### General Explanation
45. "what is a credit card"

---

## 7. Multi-Operation Queries (3 queries)

### COUNT + FAQ
46. "how many SBI credit cards and how to apply" (COUNT + FAQ)
47. "list all HDFC loans and tell me the eligibility" (LIST + FAQ)

### COUNT + COMPARE
48. "how many home loans are there and which is best" (COUNT + RECOMMEND)

--- 

## 8. Follow-up & Context Queries (2 queries)

### Follow-ups (require chat history)
49. After "how many SBI credit cards" → "list them"
50. After "compare SBI vs HDFC home loan" → "which one is better for me"

---

## Expected Routing Results

| Query # | Query | Expected Intent | Notes |
|---------|-------|-----------------|-------|
| 1-10 | COUNT variants | COUNT | Validated against DB |
| 8 | "how many cards" | CLARIFY | Missing bank/category |
| 11-18 | LIST variants | LIST | From SQL database |
| 17 | "list cards" | CLARIFY | Missing context |
| 18 | "SBI" | CLARIFY | Too vague |
| 19-30 | FAQ variants | FAQ | Non-product targets detected |
| 25 | "how many steps to apply" | FAQ | NOT COUNT (non-product target) |
| 30 | "how many times can I withdraw" | FAQ | NOT COUNT (non-product target) |
| 31-36 | COMPARE variants | COMPARE | LLM with retrieval |
| 37-41 | RECOMMEND variants | RECOMMEND | LLM analysis |
| 42-45 | EXPLAIN variants | EXPLAIN | Product details |
| 46-48 | Multi-operation | Multiple | Execute both operations |
| 49-50 | Follow-ups | Context-based | Requires history |

---

## Testing Instructions

### Manual Testing
```bash
# Start the app
streamlit run app.py

# Test each query type
# Check response accuracy and routing path
```

### Automated Testing
```python
from src.smart_router import smart_route

test_queries = [
    ("how many SBI credit cards", "COUNT"),
    ("how many steps to apply", "FAQ"),
    ("how many SBI cards and how to apply", ["COUNT", "FAQ"]),
    # ... add more
]

for query, expected in test_queries:
    result = smart_route(query)
    actual = result['intent']
    print(f"{'✅' if actual == expected else '❌'} {query}")
```

---

## Critical Test Cases

### Must Pass (Zero Tolerance)
- ✅ "how many steps to apply" → FAQ (NOT COUNT)
- ✅ "how many documents needed" → FAQ (NOT COUNT)
- ✅ "how many times can I withdraw" → FAQ (NOT COUNT)
- ✅ "how many SBI credit cards" → COUNT (accurate count)
- ✅ "how many SBI cards and how to apply" → Multi-op [COUNT, FAQ]

### Should Pass (High Priority)
- ✅ Vague queries trigger CLARIFY
- ✅ COUNT returns exact numbers from DB
- ✅ LIST never misses products
- ✅ FAQ provides accurate procedural info
- ✅ COMPARE shows all requested banks

### Nice to Have
- ✅ Follow-ups maintain context
- ✅ Natural language variations work
- ✅ Multi-bank queries handled correctly
