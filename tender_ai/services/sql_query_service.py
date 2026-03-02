# -*- coding: utf-8 -*-
import logging
import re
from .gemini_service import generate_with_gemini

_logger = logging.getLogger(__name__)

def generate_sql_from_query(env, model_names, question):
    """
    Generates a SQL query by providing the AI with schema of multiple related models.
    model_names: list of model names (e.g. ['ddn.property.info', 'ddn.property.survey'])
    """
    schema_descriptions = []
    
    for model_name in model_names:
        model = env[model_name]
        fields_list = []
        for name, field in model._fields.items():
            if field.store and name not in ['create_uid', 'write_uid', 'create_date', 'write_date']:
                rel = f" (points to {field.comodel_name})" if field.type in ['many2one', 'one2many', 'many2many'] else ""
                fields_list.append(f"  - {name} ({field.type}){rel}: {field.string}")
        
        schema_descriptions.append(
            f"MODEL: {model_name}\n"
            f"TABLE: {model._table}\n"
            f"FIELDS:\n" + "\n".join(fields_list)
        )
    
    all_schemas = "\n\n".join(schema_descriptions)

    prompt = f"""
You are a Senior Odoo Database Expert.
Your goal is to write a READ-ONLY Postgres SQL query for Odoo based on the question.

DATABASE SCHEMA:
{all_schemas}

RULES:
1. Use JOINs where necessary (e.g. joining property info with survey data using IDs).
2. Odoo Many2one fields store the ID of the related record.
3. Return ONLY the raw SQL query. No explanation, no markdown.
4. Security: ONLY SELECT statements.

USER QUESTION: {question}

SQL QUERY:"""

    try:
        res = generate_with_gemini(prompt, model="gemini-2.0-flash-lite", temperature=0.0, env=env)
        sql = (res.get('text') if isinstance(res, dict) else str(res)).strip()
        sql = re.sub(r'```sql|```', '', sql).strip()
        
        if not sql.lower().startswith('select'):
            return None, "Only SELECT queries are allowed."

        return sql, None
    except Exception as e:
        return None, str(e)

def execute_ai_sql(env, sql):
    """Executes the generated SQL safely."""
    try:
        env.cr.execute(sql)
        results = env.cr.dictfetchall()
        return results, None
    except Exception as e:
        _logger.error("SQL Execution Error: %s", str(e))
        return None, str(e)
