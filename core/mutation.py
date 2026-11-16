import re


class MutationCatalog:
    # 18+ Injected Regressions
    REGRESSION_MUTATIONS = [
        # Prompt regressions: drop rules, reorder instructions, format shifts
        {
            "id": "mut_drop_json_rule",
            "target": "prompts/entity_extractor.md",
            "category": "prompt_drop_rule",
            "desc": "Drop strict JSON formatting rule and schema constraints",
            "apply": lambda text: re.sub(r"(?i)Return ONLY a valid JSON.*?\n", "", text),
        },
        {
            "id": "mut_reorder_sentiment_instructions",
            "target": "prompts/sentiment_classifier.md",
            "category": "prompt_reorder",
            "desc": "Move input text to the top and bury output label rules at bottom",
            "apply": lambda text: "Input:\n{input}\n\nOutput labels: POSITIVE, NEGATIVE, NEUTRAL\n" + text,
        },
        {
            "id": "mut_contradict_label_rule",
            "target": "prompts/sentiment_classifier.md",
            "category": "prompt_contradiction",
            "desc": "Add contradictory instruction to also provide detailed justification",
            "apply": lambda text: text + "\nAlso provide a 3-sentence detailed justification for your choice.",
        },
        {
            "id": "mut_relax_word_count",
            "target": "prompts/short_summarizer.md",
            "category": "prompt_drop_rule",
            "desc": "Change word limit from 40 words to 250 words",
            "apply": lambda text: text.replace("40 words", "250 words"),
        },
        {
            "id": "mut_change_output_format_xml",
            "target": "prompts/entity_extractor.md",
            "category": "prompt_format_shift",
            "desc": "Instruct output to be XML tags instead of raw JSON",
            "apply": lambda text: text.replace("JSON", "XML tags <entity>...</entity>"),
        },
        {
            "id": "mut_sentiment_allow_scores",
            "target": "prompts/sentiment_classifier.md",
            "category": "prompt_format_shift",
            "desc": "Instruct output to be numeric float scores (0.0 to 1.0)",
            "apply": lambda text: text + "\nReturn a numeric float score between 0.0 and 1.0 instead of POSITIVE/NEGATIVE/NEUTRAL.",
        },
        {
            "id": "mut_summary_remove_conciseness",
            "target": "prompts/short_summarizer.md",
            "category": "prompt_drop_rule",
            "desc": "Remove brevity and conciseness requirement",
            "apply": lambda text: re.sub(r"(?i)maximum.*?words", "as long as necessary", text),
        },
        {
            "id": "mut_entity_omit_keys",
            "target": "prompts/entity_extractor.md",
            "category": "prompt_schema_break",
            "desc": "Rename schema key entities to data_items",
            "apply": lambda text: text.replace('"entities"', '"data_items"'),
        },
        {
            "id": "mut_sentiment_conversational",
            "target": "prompts/sentiment_classifier.md",
            "category": "prompt_conversational",
            "desc": "Force polite conversational prefix before the label",
            "apply": lambda text: text + "\nAlways answer conversationally starting with 'The sentiment appears to be...'",
        },
        {
            "id": "mut_summary_bullet_points",
            "target": "prompts/short_summarizer.md",
            "category": "prompt_format_break",
            "desc": "Force output into verbose multi-level nested markdown bullet points",
            "apply": lambda text: text + "\nFormat the summary as extensive bullet points under a '## Key Points' header.",
        },
        {
            "id": "mut_entity_prose_wrapping",
            "target": "prompts/entity_extractor.md",
            "category": "prompt_conversational",
            "desc": "Introduce conversational greeting and summary paragraph",
            "apply": lambda text: text + "\nBegin with a friendly introduction summarizing the document context.",
        },
        {
            "id": "mut_reorder_summary_rules",
            "target": "prompts/short_summarizer.md",
            "category": "prompt_reorder",
            "desc": "Reorder rules to put word limit last after narrative instructions",
            "apply": lambda text: "Summarize everything thoroughly.\n" + text.replace("40 words", "detailed points"),
        },

        # Skill regressions: truncate SKILL.md, weaken description
        {
            "id": "mut_truncate_sql_skill",
            "target": "skills/write-sql/SKILL.md",
            "category": "skill_truncate",
            "desc": "Truncate write-sql description to a single generic word 'Database'",
            "apply": lambda text: re.sub(r"description:\s*.*?\n", "description: Database\n", text),
        },
        {
            "id": "mut_corrupt_translate_skill",
            "target": "skills/translate-text/SKILL.md",
            "category": "skill_weaken_desc",
            "desc": "Change translation skill description to general text formatting",
            "apply": lambda text: re.sub(r"description:\s*.*?\n", "description: Format and tidy up punctuation.\n", text),
        },
        {
            "id": "mut_weaken_email_skill",
            "target": "skills/draft-email/SKILL.md",
            "category": "skill_weaken_desc",
            "desc": "Weaken email drafting description into generic file organizer",
            "apply": lambda text: re.sub(r"description:\s*.*?\n", "description: Organize and clean text files.\n", text),
        },
        {
            "id": "mut_truncate_explain_code",
            "target": "skills/explain-code/SKILL.md",
            "category": "skill_truncate",
            "desc": "Truncate explain-code description to generic conversational bot",
            "apply": lambda text: re.sub(r"description:\s*.*?\n", "description: Chat assistant.\n", text),
        },
        {
            "id": "mut_weaken_summarize_skill",
            "target": "skills/summarize-text/SKILL.md",
            "category": "skill_weaken_desc",
            "desc": "Restrict summarize-text description exclusively to cooking recipes",
            "apply": lambda text: re.sub(r"description:\s*.*?\n", "description: Summarize cooking recipes and grocery lists.\n", text),
        },

        # Model swap regression
        {
            "id": "mut_model_swap_smaller",
            "target": "models.yaml",
            "category": "model_swap",
            "desc": "Swap default model to a smaller or higher-temperature setting that degrades compliance",
            "apply": lambda text: text.replace("temperature: 0.7", "temperature: 1.5"),
        },
    ]

    # 8 Benign controls (should NOT trigger a BLOCK verdict)
    BENIGN_CONTROLS = [
        {
            "id": "benign_whitespace_sentiment",
            "target": "prompts/sentiment_classifier.md",
            "category": "whitespace",
            "desc": "Add harmless trailing whitespace and blank lines",
            "apply": lambda text: text + "\n\n   \n\n",
        },
        {
            "id": "benign_paraphrase_summary",
            "target": "prompts/short_summarizer.md",
            "category": "paraphrase",
            "desc": "Paraphrase 'strictly' to 'carefully' and 'concise' to 'brief'",
            "apply": lambda text: text.replace("strictly", "carefully").replace("concise", "brief"),
        },
        {
            "id": "benign_heading_rename_entity",
            "target": "prompts/entity_extractor.md",
            "category": "heading_rename",
            "desc": "Rename internal prompt comment header",
            "apply": lambda text: "<!-- Production entity prompt revision -->\n" + text,
        },
        {
            "id": "benign_reorder_examples_sql",
            "target": "skills/write-sql/SKILL.md",
            "category": "reordered_examples",
            "desc": "Reorder markdown example bullet points in write-sql body",
            "apply": lambda text: text.replace("- SELECT", "  * SELECT"),
        },
        {
            "id": "benign_synonym_extractor",
            "target": "prompts/entity_extractor.md",
            "category": "paraphrase",
            "desc": "Swap 'identify' with 'locate' in instruction text",
            "apply": lambda text: text.replace("identify", "locate").replace("Identify", "Locate"),
        },
        {
            "id": "benign_comment_sentiment",
            "target": "prompts/sentiment_classifier.md",
            "category": "whitespace",
            "desc": "Add harmless developer comment line",
            "apply": lambda text: "# Classification prompt\n" + text,
        },
        {
            "id": "benign_heading_rename_skill",
            "target": "skills/explain-code/SKILL.md",
            "category": "heading_rename",
            "desc": "Rename heading in explain-code body from # Explain Code to # Code Explanation",
            "apply": lambda text: text.replace("# Explain Code Skill", "# Code Explanation Skill"),
        },
        {
            "id": "benign_reorder_examples_email",
            "target": "skills/draft-email/SKILL.md",
            "category": "reordered_examples",
            "desc": "Reorder bullet examples in draft-email body",
            "apply": lambda text: text.replace("formal announcements", "announcements and updates"),
        },
    ]


def get_all_mutations():
    return MutationCatalog.REGRESSION_MUTATIONS + MutationCatalog.BENIGN_CONTROLS
