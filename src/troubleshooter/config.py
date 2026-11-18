"""App settings. Kept here so no path, number or model name is hard-coded elsewhere."""

from pathlib import Path

SAMPLES_DIR = Path(__file__).with_name("samples")

REPO_URL = "https://github.com/io-sar/ai-generated-project-troubleshooter"
# Links point at develop until release 0.1 puts the docs on main; the roadmap's
# release checklist switches this.
DOCS_BRANCH = "develop"
BOARD_URL = "https://github.com/users/io-sar/projects/5"
BUILDER_LINKEDIN_URL = "https://www.linkedin.com/in/ioannis-sarantidis-52367a74/"

# Page paths are relative to the app root, as st.navigation and st.page_link expect.
ANALYZE_PAGE = "app_pages/analyze.py"
HOW_BUILT_PAGE = "app_pages/how_it_was_built.py"
