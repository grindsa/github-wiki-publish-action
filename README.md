# Github Wiki Publish Action

This [GitHub Action][github actions]
publishes markdown documentation to your project's [wiki][github wiki]
from a workflow.

Page titles come from an HTML comment in each file. GitHub Wiki uses the
filename as the visible page headline, so the action copies each document to
`{slug}.md`.

```html
<!-- wiki-title: External Account Binding -->
<!-- wiki-category: Features -->
```

`wiki-title:` and `wiki-title` are both accepted. A leading `#` in the title is
stripped. If the comment is missing, the first `#` heading is used.

## Usage

```yml
name: Documentation

on: [push]

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
      - name: Upload Documentation to Wiki
        uses: grindsa/github-wiki-publish-action@customize_wiki_title
        with:
          path: |
            docs
            examples/Docker
          exclude: architecture/**
          generate-home: true
          generate-sidebar: true
          sync: true
        env:
          GH_PERSONAL_ACCESS_TOKEN: ${{ secrets.GH_PERSONAL_ACCESS_TOKEN }}
```

### Inputs

| Input | Default | Description |
| --- | --- | --- |
| `path` | required | Directory, or newline/comma-separated directories |
| `recursive` | `false` | Include markdown files in subdirectories |
| `exclude` | _empty_ | Glob patterns matched from each source root |
| `generate-home` | `false` | Write `Home.md` grouped by `wiki-category` |
| `generate-sidebar` | `false` | Write `_Sidebar.md` (often hidden in GitHub's current wiki UI) |
| `inject-nav` | `true` | Insert a grouped navigation block into every wiki page |
| `home-title` | repository name | Title on Home.md |
| `home-intro` | _empty_ | Markdown inserted below the Home title |
| `sidebar-title` | `Navigation` | Heading at the top of `_Sidebar.md` |
| `category-order` | Installation, High Availability, CA Handlers, Features, Configuration, Operations, Development, Architecture, Other | Category heading order |
| `sync` | `false` | Delete wiki markdown pages that were not produced from the source docs |
| `copy-assets` | `true` | Copy image files from the source directories |

Internal markdown links (`[text](other.md#anchor)`) are rewritten to the
published wiki slugs. Relative links that resolve to another published file are
included.

With `inject-nav: true` (the default) each wiki page gets a grouped
navigation block after its title. GitHub's current wiki UI no longer renders
`_Sidebar.md` as a side column, so the in-page nav is what readers see.
`generate-sidebar: true` still writes `_Sidebar.md` for older wiki layouts.

## Setup

This GitHub action requires that your repository has the following:

- A wiki with at least one page in it
- A secret named `GH_PERSONAL_ACCESS_TOKEN`
  with a Github personal access token with "repo" authorization

Follow the steps below to ensure that everything's configured correctly.

> **Note**
> GitHub doesn't currently provide APIs for interacting with project wikis,
> so much of the required setup must be done manually.

### 1. Enable Your Repository's Wikis Feature

Navigate to the "Settings" tab for your repository,
scroll down to the "Features" section,
and ensure that the checkbox labeled "Wikis" is checked.

### 2. Create the First Wiki Page

With the Wikis feature enabled for your repository,
navigate to the "Wiki" tab.
If prompted,
create the first wiki page.

### 3. Generate a Personal Access Token

Navigate to the [Personal access tokens](https://github.com/settings/tokens) page
in your GitHub account settings
(Settings > Developer settings > Personal access tokens)
and click the "Generate a new token" button.

In the "New personal access token" form,
provide a descriptive comment in the "Note" field, like "Wiki Management".
Under "Select scopes",
enable all of the entries under "repo" perms.

When you're done,
click the "Generate token" button at the bottom of the form.

> **Note**:
> GitHub actions have access to [a `GITHUB_TOKEN` secret][GITHUB_TOKEN],
> but that token's permissions are limited to
> the repository that contains your workflow.
> This workflow requires the generation of a new personal acccess token
> to read and write to the git repository for your project's wiki.

### 4. Set a Repository Secret

Copy your generated personal access token to the clipboard
and navigate to your project settings.
Navigate to the "Secrets" page,
click "Add a new secret",
and fill in the form by
entering `GH_PERSONAL_ACCESS_TOKEN` into the "Name" field and
pasting your token into the "Value" field.

## License

MIT

## Contact

Mattt ([@mattt](https://twitter.com/mattt))

[github actions]: https://help.github.com/en/actions
[github wiki]: https://help.github.com/en/github/building-a-strong-community/about-wikis
[GITHUB_TOKEN]: https://help.github.com/en/actions/automating-your-workflow-with-github-actions/authenticating-with-the-github_token#about-the-github_token-secret
