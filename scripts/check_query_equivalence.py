from dapuria import RecipeService, Settings

service = RecipeService(Settings())

queries = [
    "telur, tahu",
    "telur dan tahu",
    "telur; tahu",
]

for query in queries:
    result = service.handle_user_input(query)

    print("\nQUERY:", query)
    print("PARSED:", result.get("user_ingredients"))

    if result["status"] == "ok":
        for rank, row in enumerate(result["results"], 1):
            print(
                rank,
                row["id"],
                row["title"],
                f"{row['final_score']:.4f}",
            )
