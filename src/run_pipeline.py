"""Run the full pipeline: generate -> clean -> load to SQL + KPI exports."""
import clean_data
import generate_data
import load_to_sql

if __name__ == "__main__":
    generate_data.main()
    clean_data.main()
    load_to_sql.main()
