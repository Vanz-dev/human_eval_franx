import os
import pandas as pd

columns = ["session_name", "timestamp", "article_id", "lang", "entity_mention", "main_role", 
           "predicted_roles", "makes_sense", "issues", "multi_labels", "confidence"]

for lang in ["en", "hi", "pt", "bg", "ru"]:  # Add your language codes here
    output_file = f"responses_{lang}.csv"
    if not os.path.exists(output_file):
        pd.DataFrame(columns=columns).to_csv(output_file, index=False)
