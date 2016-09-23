# Core modules
import re
import tempfile
from copy import deepcopy
from glob import iglob
from os import makedirs, path
from urllib.parse import urlsplit, urlunsplit

# Third party modules
import frontmatter
import markdown
import yaml
from git import Repo
from jinja2 import Template

# Local modules
from .utilities import mergetree

# Configuration
# ==
default_title = 'Juju Documentation'
markdown_extensions = [
    'markdown.extensions.meta',
    'markdown.extensions.tables',
    'markdown.extensions.fenced_code',
    'markdown.extensions.def_list',
    'markdown.extensions.attr_list',
    'markdown.extensions.toc',
    'callouts',
    'anchors_away',
    'foldouts'
]
default_template = path.join(
    path.dirname(__file__),
    'resources',
    'wrapper.jinja2'
)


def parse_markdown(filepath):
    """
    Parse an individual markdown file to HTML, also returning
    the meta title
    """

    markdown_parser = markdown.Markdown(extensions=markdown_extensions)
    file_parts = frontmatter.load(filepath)
    html_content = markdown_parser.convert(file_parts.content)

    return (html_content, file_parts.metadata)


class Builder:
    """
    Parse a remote git repository of markdown files into HTML files in the
    specified build folder
    """

    def __init__(
        self,
        source_path,
        source_media_path,
        source_context_path,
        output_path,
        output_media_path,
        template,
        global_context,
        media_url,
        no_link_extensions
    ):
        self.source_path = source_path
        self.source_media_path = source_media_path
        self.output_path = output_path
        self.output_media_path = output_media_path
        self.template = template
        self.global_context = global_context
        self.media_url = media_url
        self.no_link_extensions = no_link_extensions

    def build_files(self):
        """
        Given a folder of markdown files,
        parse all files into a new folder of HTML files
        """

        if path.relpath(self.source_media_path, self.output_media_path) != '.':
            mergetree(self.source_media_path, self.output_media_path)
            print(
                "Copied {} to {}".format(
                    self.source_media_path, self.output_media_path
                )
            )

        for filepath in iglob(path.join(self.source_path, '**/*.md')):
            self.build_file(filepath)

    def build_file(self, source_filepath):
        """
        Create an HTML file for a documentation page from a path to the
        corresponding Markdown file
        """

        # Get output filepath
        local_path = path.relpath(source_filepath, self.source_path)
        output_filepath = path.join(self.output_path, local_path)
        output_filepath = re.sub(r'\.md$', '.html', output_filepath)

        # Check folder exists
        makedirs(path.dirname(output_filepath), exist_ok=True)

        # Parse the markdown
        (html_contents, metadata) = parse_markdown(source_filepath)

        # Build document from template
        local_context = self.build_context(html_contents, metadata)
        html_document = self.template.render(local_context)

        # Replace media links
        if not self.media_url:
            output_dir = path.dirname(output_filepath)
            media_url = path.relpath(self.output_media_path, output_dir)

        old_media_path = path.relpath(
            self.source_media_path,
            path.dirname(source_filepath)
        )
        html_document = html_document.replace(old_media_path, media_url)

        # Replace internal document links
        if self.no_link_extensions:
            html_document = re.sub(
                r'(href="(?! *http).*)\.md',
                r'\1',
                html_document
            )
        else:
            html_document = re.sub(
                r'(href="(?! *http).*)\.md',
                r'\1.html',
                html_document
            )

        with open(output_filepath, 'w') as output_file:
            output_file.write(html_document)

        print("Created {output_filepath}".format(**locals()))

    def build_context(self, html_contents, metadata):
        """
        Construct the template context for an individual page
        """

        local_context = deepcopy(self.global_context)
        local_context.update(metadata)
        local_context['content'] = html_contents

        return local_context


def build(
    repository,
    branch,
    source_path,
    source_media_path,
    source_context_path,
    output_path,
    output_media_path,
    template_path,
    media_url,
    no_link_extensions
):
    with open(template_path or default_template) as template_file:
        template = Template(template_file.read())

    if repository:
        repo_dir = tempfile.mkdtemp()
        print("Cloning {repository} into".format(**locals()))
        if branch:
            Repo.clone_from(repository, repo_dir, branch=branch)
        else:
            Repo.clone_from(repository, repo_dir)

        source_path = path.join(repo_dir, source_path)
        source_media_path = path.join(repo_dir, source_media_path)
        source_context_path = path.join(repo_dir, source_context_path)

    with open(source_context_path) as context_file:
        global_context = yaml.load(context_file)

    builder = Builder(
        source_path=source_path,
        source_media_path=source_media_path,
        source_context_path=source_context_path,
        output_path=output_path,
        output_media_path=output_media_path,
        template=template,
        global_context=global_context,
        media_url=media_url,
        no_link_extensions=no_link_extensions
    )
    builder.build_files()
