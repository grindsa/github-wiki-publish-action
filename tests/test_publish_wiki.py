from __future__ import annotations

from pathlib import Path

import publish_wiki as wiki


def write_page(path: Path, title: str, body: str = "content", category: str | None = None) -> None:
    lines = [f"<!-- wiki-title: {title} -->"]
    if category:
        lines.append(f"<!-- wiki-category: {category} -->")
    lines.extend(["", f"# {title}", "", body, ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def test_extract_meta_accepts_colon_hash_and_legacy_name() -> None:
    colon = "<!-- wiki-title: External Account Binding -->\n# Heading\n"
    space = "<!-- wiki-title ACME CA handler -->\n# Heading\n"
    hashed = "<!-- wiki-title # Cluster guide -->\n# Heading\n"
    legacy = "<!-- wiki-name: Hooks -->\n# Heading\n"
    missing = "# Vault Handler\n"

    assert wiki.extract_meta(colon, "fallback") == ("External Account Binding", "Other")
    assert wiki.extract_meta(space, "fallback")[0] == "ACME CA handler"
    assert wiki.extract_meta(hashed, "fallback")[0] == "Cluster guide"
    assert wiki.extract_meta(legacy, "fallback")[0] == "Hooks"
    assert wiki.extract_meta(missing, "fallback")[0] == "Vault Handler"


def test_env_or_default_accepts_docker_hyphenated_input_names(monkeypatch) -> None:
    monkeypatch.setenv("INPUT_GENERATE-HOME", "true")
    monkeypatch.delenv("INPUT_GENERATE_HOME", raising=False)
    assert wiki.parse_bool(wiki.env_or_default("INPUT_GENERATE_HOME"), False) is True


def test_slugify_strips_markup_and_unsafe_filename_chars() -> None:
    assert wiki.slugify("# How to build a cluster") == "How-to-build-a-cluster"
    assert wiki.slugify("Asynchronous Mode (`async_mode`)") == "Asynchronous-Mode-async_mode"
    assert (
        wiki.slugify("Prevalidated Domain/IP/Email List")
        == "Prevalidated-Domain-IP-Email-List"
    )
    assert wiki.slugify("Installation from PyPI on Apache2 (Ubuntu)") == (
        "Installation-from-PyPI-on-Apache2-Ubuntu"
    )


def test_publish_renames_pages_rewrites_links_and_builds_home(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    write_page(
        docs / "eab.md",
        "External Account Binding",
        "See [housekeeping](housekeeping.md#reports) and [vault](../handlers/vault.md).",
        "Features",
    )
    write_page(
        docs / "housekeeping.md",
        "Reporting and Housekeeping",
        "Back to [EAB](eab.md).",
        "Operations",
    )
    handlers = tmp_path / "handlers"
    handlers.mkdir()
    write_page(handlers / "vault.md", "Hashicorp Vault PKI CA-handler", "Vault docs.", "CA Handlers")
    dest = tmp_path / "wiki"

    config = wiki.PublishConfig(
        sources=[docs, handlers],
        dest=dest,
        workspace=tmp_path,
        generate_home=True,
        generate_sidebar=True,
        home_title="Welcome to the acme2certifier wiki",
        home_intro="",
        sync=True,
    )
    pages = wiki.publish(config)
    slugs = {page.slug for page in pages}

    assert slugs == {
        "External-Account-Binding",
        "Reporting-and-Housekeeping",
        "Hashicorp-Vault-PKI-CA-handler",
    }
    eab = (dest / "External-Account-Binding.md").read_text(encoding="utf-8")
    assert "[housekeeping](Reporting-and-Housekeeping#reports)" in eab
    assert "[vault](Hashicorp-Vault-PKI-CA-handler)" in eab
    assert eab.index("# External Account Binding") < eab.index("**Navigation**")
    assert "- **Operations**" in eab
    assert "  - [Reporting and Housekeeping](Reporting-and-Housekeeping)" in eab
    assert '<table align="right">' not in eab

    home = (dest / "Home.md").read_text(encoding="utf-8")
    assert home.startswith("# Welcome to the acme2certifier wiki\n")
    assert home.index("## CA Handlers") < home.index("## Features") < home.index("## Operations")
    assert "- [External Account Binding](External-Account-Binding)" in home
    sidebar = (dest / "_Sidebar.md").read_text(encoding="utf-8")
    assert sidebar.startswith("# Navigation\n")
    assert "- [Home](Home)" in sidebar
    assert "- **Operations**" in sidebar
    assert "  - [Reporting and Housekeeping](Reporting-and-Housekeeping)" in sidebar
    assert sidebar.index("- **CA Handlers**") < sidebar.index("- **Features**") < sidebar.index(
        "- **Operations**"
    )


def test_exclude_and_sync_remove_unpublished_pages(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    (docs / "architecture").mkdir(parents=True)
    write_page(docs / "install_deb.md", "DEB Installation", "Install.", "Installation")
    write_page(docs / "architecture" / "layout.md", "Package layout", "Internal.", "Architecture")
    dest = tmp_path / "wiki"
    dest.mkdir()
    (dest / "Stale-Page.md").write_text("gone", encoding="utf-8")
    (dest / "Home.md").write_text("old home", encoding="utf-8")

    wiki.publish(
        wiki.PublishConfig(
            sources=[docs],
            dest=dest,
            workspace=tmp_path,
            recursive=True,
            exclude=["architecture/**"],
            generate_home=True,
            home_title="Wiki",
            sync=True,
        )
    )

    names = {path.name for path in dest.glob("*.md")}
    assert names == {"DEB-Installation.md", "Home.md"}
    assert "Package layout" not in (dest / "Home.md").read_text(encoding="utf-8")
