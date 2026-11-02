from dapuria import RecipeService, Settings

service = RecipeService(Settings())

query = "2 butir telur, 100 gr dada ayam, 2 siung bawang putih"

results, parsed = service.rerank(query, top_n=10)

print("Parsed:", parsed)
print("T_relevansi:", min(2, len(parsed)))
print()

for rank, recipe in enumerate(results, 1):
    print(
        rank,
        recipe["title"],
        f"score={recipe['final_score']:.4f}",
        f"matched={recipe['matched_user_items']}",
        f"coverage_user={recipe['coverage_user']:.3f}",
        f"source={recipe['retrieval_source']}",
    )
