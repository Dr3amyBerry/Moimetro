"""Static UI contract tests: keep API bindings intact during visual redesign."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/styles.css").read_text(encoding="utf-8")


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.tabs = []
        self.scripts = []
        self.forms = []
        self.views = []

    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        if "id" in props:
            self.ids.append(props["id"])
        if tag == "button" and props.get("data-view"):
            self.tabs.append(props["data-view"])
        if tag == "script":
            self.scripts.append(props.get("src"))
        if tag == "form":
            self.forms.append(props.get("id"))
        if props.get("class") == "view-panel":
            self.views.append(props.get("id"))


def document():
    structure = Structure()
    structure.feed(HTML)
    return structure


def test_unique_ids_and_all_javascript_bindings_exist():
    page = document()
    duplicates = [key for key, count in Counter(page.ids).items() if count > 1]
    assert not duplicates, f"IDs duplicados: {duplicates}"
    required = set(re.findall(r'\bel\(["\']([^"\']+)["\']\)', JS))
    missing = required - set(page.ids)
    assert not missing, f"UI necesita elementos que no existen: {missing}"


def test_three_simple_sections_and_all_forms():
    page = document()
    assert page.tabs == ["overview", "profile", "consultation"]
    assert set(page.views) == {"viewOverview", "viewProfile", "viewEncounter"}
    assert {"loginForm", "patientForm", "staffForm", "patientEditForm",
            "historyForm", "encounterForm", "manualForm",
            "clinicalForm"}.issubset(set(page.forms))
    assert 'setActiveView("consultation")' in JS
    assert 'setActiveView("overview")' in JS


def test_offline_ui_has_no_third_party_scripts_or_inline_js():
    page = document()
    assert page.scripts == ["/static/app.js"]
    assert "https://" not in HTML
    assert "http://" not in HTML
    assert "<style" not in HTML
    assert "onclick=" not in HTML
    assert "url(http" not in CSS


def test_visual_theme_is_grayscale_and_accessible():
    assert "--sidebar: #292c31" in CSS
    assert "--canvas: #f4f5f6" in CSS
    assert ":focus-visible" in CSS
    assert "@media (max-width: 650px)" in CSS
    assert 'aria-label="Secciones del expediente"' in HTML


def test_enterprise_directory_replaces_demo_sidebar():
    page = document()
    for required in ("directoryScreen", "directoryNext", "directoryPrev",
                     "directoryDocumentType", "directoryPageLabel",
                     "registrationScreen", "patientScreen", "navPatients",
                     "navStaff", "visitListNext", "visitListPrev"):
        assert required in page.ids, required
    assert "newPatientDetails" not in page.ids
    assert 'id="patientList"' in HTML
    assert '/api/patients/directory?' in JS
    assert '/api/encounters/directory?' in JS
    assert "DIRECTORY_LIMIT = 25" in JS
    assert "VISIT_LIMIT = 15" in JS
    assert "directory.next" in JS
    assert "visits.next" in JS
    assert "staffList" in page.ids
    assert "staffNext" in page.ids
    assert "staffCreatePanel" in page.ids
    assert '/api/admin/users?' in JS
    assert "textContent = patient.full_name" in JS


def test_security_and_traceability_controls_in_interface():
    page = document()
    required = {"changePasswordButton", "accountPanel", "passwordForm",
                "staffManageForm", "staffManagePanel", "cancelStaffManage",
                "staffManageTitle", "revisionPanel", "revisionList",
                "revisionNext", "revisionPrev", "revisionPageLabel"}
    assert required.issubset(set(page.ids)), required - set(page.ids)
    assert "passwordForm" in page.forms
    assert "staffManageForm" in page.forms
    assert "/api/auth/change-password" in JS
    assert "/api/admin/users/" in JS
    assert "/revisions?" in JS
    assert "textContent = entry" not in JS  # metadata is composed safely
    assert "innerHTML" not in JS
