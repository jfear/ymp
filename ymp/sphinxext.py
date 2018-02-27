"""This module contains a Sphinx_ extension for documenting YMP stages and
Snakemake_ rules.

The `SnakemakeDomain` (name **sm**) provides the following directives:

.. rst:directive:: .. sm:rule:: name

   Describes a `Snakemake rule <snakefiles-rules>`

.. rst:directive:: .. sm:stage:: name

   Describes a `YMP Stage <Stage>`

Both directives accept an optional ``source`` parameter. If given, a
link to the source code of the stage or rule definition will be added.
The format of the string passed is ``filename:line``. Referenced
Snakefiles will be highlighted with pygments and added to the
documentation when building HTML.

The extension also provides an autodoc-like directive:

.. rst:directive:: .. autosnake:: filename

   Generates documentation from Snakefile ``filename``.

.. _Sphinx: http://sphinx-doc.org
.. _Snakemake: http://snakemake.readthedocs.io

"""

import os
from textwrap import dedent, indent
from typing import List, Optional

from docutils import nodes
from docutils.parsers import rst
from docutils.statemachine import StringList

from snakemake.rules import Rule

from sphinx import addnodes
from sphinx.application import Sphinx
from sphinx.directives import ObjectDescription
from sphinx.domains import Domain, ObjType
from sphinx.environment import BuildEnvironment
from sphinx.environment.collectors import EnvironmentCollector
from sphinx.roles import XRefRole
from sphinx.util import logging, ws_re
from sphinx.util.nodes import make_refnode

import ymp
from ymp.snakemake import ExpandableWorkflow
from ymp.snakemakelexer import SnakemakeLexer
from ymp.stage import Stage

try:
    logger = logging.getLogger(__name__)
except AttributeError:
    # Fall back to normal logging
    import logging as _logging
    logger = _logging.getLogger(__name__)

#: str: Path in which YMP package is located
BASEPATH = os.path.dirname(os.path.dirname(ymp.__file__))


def relpath(path: str) -> str:
    """Make absolute path relative to BASEPATH

    Args:
      path: absolute path

    Returns:
      path relative to BASEPATH
    """
    return os.path.relpath(path, BASEPATH)


class YmpObjectDescription(ObjectDescription):
    """
    Base class for RSt directives in SnakemakeDomain

    Since this inherhits from Sphinx' ObjectDescription, content
    generated by the directive will always be inside an addnodes.desc.

    Args:
      source: Specify source position as ``file:line`` to create link
    """
    typename = "[object name]"

    option_spec = {
        # source link (<filename>:<lineno>)
        'source': rst.directives.unchanged
    }

    def handle_signature(self, sig: str, signode: addnodes.desc) -> str:
        """
        Parse rule signature *sig* into RST nodes and append them
        to *signode*.

        The retun value identifies the object and is passed to
        :meth:`add_target_and_index()` unchanged

        Args:
          sig: Signature string (i.e. string passed after directive)
          signode: Node created for object signature
        Returns:
          Normalized signature (white space removed)
        """
        signode += addnodes.desc_annotation(self.typename, self.typename+" ")
        signode += addnodes.desc_name(sig, sig)

        if 'source' in self.options:
            self.add_source_link(signode)

        sigid = ws_re.sub('', sig)
        return sigid

    def add_source_link(self, signode: addnodes.desc) -> None:
        """
        Add link to source code to `signode`
        """
        filename, lineno = self.options['source'].split(':')
        if not hasattr(self.env, '_snakefiles'):
            self.env._snakefiles = set()
        self.env._snakefiles.add(filename)

        onlynode = addnodes.only(expr='html')  # show only in html
        onlynode += nodes.reference(
            '',
            refuri='_snakefiles/{}.html#line-{}'.format(filename, lineno)
        )
        onlynode[0] += nodes.inline('', '[source]',
                                    classes=['viewcode-link'])
        signode += onlynode

    def add_target_and_index(self, name: str, sig: str,
                             signode: addnodes.desc) -> None:
        """
        Add cross-reference IDs and entries to `self.indexnode`
        """
        targetname = "-".join((self.objtype, name))
        if targetname not in self.state.document.ids:
            signode['names'].append(targetname)
            signode['ids'].append(targetname)
            signode['first'] = (not self.names)
            self.state.document.note_explicit_target(signode)

            objects = self.env.domaindata[self.domain]['objects']
            key = (self.objtype, name)
            if key in objects:
                self.env.warn(self.env.docname,
                              'duplicate description of {} {}, '
                              'other instance in {}:{}'
                              ''.format(self.objtype, name,
                                        self.env.doc2path(objects[key][0]),
                                        self.lineno))
            objects[key] = (self.env.docname, targetname)

        # register rule in index
        indextext = self.get_index_text(self.objtype, name)
        if indextext:
            self.indexnode['entries'].append((
                'single',
                indextext,
                targetname,
                '',
                None))

    def get_index_text(self, typename: str, name: str) -> str:
        """Formats object for entry into index"""
        return "{} ({})".format(name, typename)


class SnakemakeRule(YmpObjectDescription):
    """
    Directive `sm:rule::` describing a Snakemake rule
    """
    typename = "rule"


class YmpStage(YmpObjectDescription):
    """
    Directive `sm:stage::` describing an YMP stage
    """
    typename = "stage"


class SnakemakeDomain(Domain):
    """Snakemake language domain"""
    name = "sm"
    label = "Snakemake"

    object_types = {
        # ObjType(name, *roles, **attrs)
        'rule': ObjType('rule', 'rule'),
        'stage': ObjType('stage', 'stage'),
    }
    directives = {
        'rule': SnakemakeRule,
        'stage': YmpStage,
    }
    roles = {
        'rule': XRefRole(),
        'stage': XRefRole(),
    }
    initial_data = {
        'objects': {},  #: (type, name) -> docname, labelid
    }

    data_version = 0

    def clear_doc(self, docname: str):
        """Delete objects derived from file ``docname``"""
        if 'objects' in self.data:
            toremove = [
                key
                for (key, (docname_, _)) in self.data['objects'].items()
                if docname_ == docname
            ]
            for key in toremove:
                del self.data['objects'][key]

    def resolve_xref(self, env: BuildEnvironment, fromdocname: str,
                     builder, typ, target, node, contnode):
        objects = self.data['objects']
        objtypes = self.objtypes_for_role(typ)
        for objtype in objtypes:
            if (objtype, target) in objects:
                return make_refnode(builder, fromdocname,
                                    objects[objtype, target][0],
                                    objects[objtype, target][1],
                                    contnode, target + ' ' + objtype)

    def get_objects(self):
        for (typ, name), (docname, ref) in self.data['objects'].items():
            # name, dispname, type, docname, anchor, searchprio
            yield name, name, typ, docname, ref, 1


class AutoSnakefileDirective(rst.Directive):
    """Implements RSt directive ``.. autosnake:: filename``

    The directive extracts docstrings from rules in snakefile and
    auto-generates documentation.
    """

    #: bool: This rule does not accept content
    has_content = False

    #: int: This rule needs one argument (the filename)
    required_arguments = 1

    #: str: Template for generated Rule RSt
    tpl_rule = dedent("""
    .. sm:rule:: {name}
       :source: {filename}:{lineno}
    """)

    #: str: Template for generated Stage RSt
    tpl_stage = dedent("""
    .. sm:stage:: {name}
       :source: {filename}:{lineno}
    """)

    def run(self):
        """Entry point"""
        snakefile = self.arguments[0]

        #: BuildEnvironment: Sphinx build environment
        self.env: BuildEnvironment = self.state.document.settings.env

        #: ExpandableWorkflow: Ymp Workflow object
        self.workflow = self.load_workflow(snakefile)

        return self._generate_nodes()

    def load_workflow(self, file_path: str) -> ExpandableWorkflow:
        """Load the Snakefile"""
        workflow = ExpandableWorkflow(snakefile=file_path)
        workflow.include(file_path)
        return workflow

    def parse_doc(self, doc: str, source: str, idt: int=0) -> StringList:
        """Convert doc string to StringList

        Args:
          doc: Documentation text
          source: Source filename
          idt: Result indentation in characters (default 0)

        Returns:
          StringList of re-indented documentation wrapped in newlines
        """
        doc = dedent(doc or "").strip("\n")
        doc = indent(doc, " " * idt)
        doclines = [''] + doc.splitlines() + ['']
        return StringList(doclines, source)

    def parse_rule(self, rule: Rule, idt: int=0) -> StringList:
        """Convert Rule to StringList

        Args:
          rule: Rule object
          idt: Result indentation in characters (default 0)

        Retuns:
          StringList containing formatted Rule documentation
        """
        head = self.tpl_rule.format(
            name=rule.name,
            filename=relpath(rule.snakefile),
            lineno=self.workflow.linemaps[rule.snakefile][rule.lineno],
        )
        head = indent(head, " " * idt)
        headlines = head.splitlines()
        doc = self.parse_doc(rule.docstring, rule.snakefile, idt+3)

        return StringList(headlines, rule.snakefile) + doc

    def parse_stage(self, stage: Stage, idt: int=0) -> StringList:
        head = self.tpl_stage.format(
            name=stage.name,
            filename=relpath(stage.filename),
            lineno=self.workflow.linemaps[stage.filename][stage.lineno],
        )
        head = indent(head, " " * idt)
        headlines = head.splitlines()
        doc = self.parse_doc(stage.docstring, stage.filename, idt+3)

        res = StringList(headlines, stage.filename) + doc
        for rule in sorted(stage.rules, key=lambda s: s.name):
            res.extend(self.parse_rule(rule, idt+3))
        return res

    def _generate_nodes(self) -> List[nodes.Node]:
        """Generate Sphinx nodes from parsed snakefile"""
        node = nodes.paragraph('')
        result = StringList()

        # generate stages
        stages = Stage.get_stages().values()
        stages = list(set(stages))
        stages = sorted(stages, key=lambda x: x.name)
        for stage in stages:
            result.extend(self.parse_stage(stage))

        # generate nodes for rules not registered with stages
        rules = self.workflow.rules
        for rule in rules:
            if not getattr(rule, "ymp_stage", False):
                result.extend(self.parse_rule(rule))

        self.state.nested_parse(result, 0, node)
        return [node]


def collect_pages(app: Sphinx):
    """Add Snakefiles to documentation (in HTML mode)
    """
    if not hasattr(app.env, '_snakefiles'):
        return

    highlight_block = app.builder.highlighter.highlight_block

    for snakefile in app.env._snakefiles:
        try:
            with open(os.path.join("..", snakefile), 'r') as f:
                code = f.read()
        except IOError:
            logger.error("failed to open {}".format(snakefile))
            continue
        highlighted = highlight_block(code, 'snakemake', lineanchors="line")
        context = {
            'title': snakefile,
            'body': '<h1>Snakefile "{}"</h1>'.format(snakefile) +
            highlighted
        }
        yield (os.path.join('_snakefiles', snakefile), context, 'page.html')

    html = ['\n']
    context = {
        'title': ('Overview: Snakemake rule files'),
        'body': '<h1>All Snakemake rule files</h1>' +
        ''.join(html)
    }
    yield ('_snakefiles/index', context, 'page.html')


class DomainTocTreeCollector(EnvironmentCollector):
    """Add Sphinx Domain entries to the TOC"""

    # override
    def clear_doc(self, app: Sphinx,
                  env: BuildEnvironment, docname: str) -> None:
        """Clear data from environment

        If we have cached data in environment for document `docname`,
        we should clear it here.

        """

    # override
    def merge_other(self, app: Sphinx, env: BuildEnvironment,
                    docnames: List[str], other: BuildEnvironment) -> None:
        """Merge with results from parallel processes

        Called if Sphinx is processing documents in parallel. We
        should merge this from `other` into `env` for all `docnames`.
        """

    # override
    def process_doc(self, app: Sphinx, doctree: nodes.Node) -> None:
        """Process `doctree`

        This is called by `read-doctree`, so after the doctree has been
        loaded. The signal is processed in registered first order,
        so we are called after built-in extensions, such as the
        `sphinx.environment.collectors.toctree` extension building
        the TOC.
        """

        # FIXME: handle duplicate entries
        for node in self.select_doc_nodes(doctree):
            tocnode = self.select_toc_location(app, node)
            heading = self.make_heading(node)
            if not tocnode:
                continue

            self.toc_insert(app.env.docname, tocnode, node, heading)

    def select_doc_nodes(self, doctree: nodes.Node) -> List[nodes.Node]:
        """Select the nodes for which entries in the TOC are desired

        This is a separate method so that it might be overriden by
        subclasses wanting to add other types of nodes to the TOC.
        """
        return doctree.traverse(addnodes.desc)

    def select_toc_location(self, app: Sphinx,
                            node: nodes.Node) -> nodes.Node:
        """Select location in TOC where `node` should be referenced
        """
        while node is not None:
            tocnode = self.locate_in_toc(app, node)
            if tocnode:
                return tocnode

            node = node.parent
        return app.env.tocs[app.env.docname][0]

    def locate_in_toc(self, app: Sphinx,
                      node: nodes.Node) -> Optional[nodes.Node]:
        toc = app.env.tocs[app.env.docname]
        ref = self.get_ref(node)
        for node in toc.traverse(nodes.reference):
            node_ref = node.get('anchorname')
            if not node_ref or node_ref[0] != "#":
                continue
            if node_ref[1:] == ref:
                return node.parent.parent

    def get_ref(self, node: nodes.Node) -> Optional[nodes.Node]:
        while node is not None:
            if not node.get('ids'):
                # In Sphinx domain descriptions, the ID is in the
                # first child node, the desc_signature.
                # We can take that, but to make the JS handling
                # the TOC sidebar work properly, we need it to
                # be in the hierarchy. So create an ID for the
                # desc node.
                if node[0].get('ids'):
                    node['ids'] = [node[0].get('ids')[0] + '-tocentry']
            if node.get('ids'):
                return node['ids'][0]
            node = node.parent

    def make_heading(self, node: nodes.Node) -> List[nodes.Node]:
        names = node[0].traverse(addnodes.desc_name)
        return names

    def toc_insert(self, docname: str, tocnode: nodes.Node, node: nodes.Node,
                   heading: List[nodes.Node]) -> None:
        for child in tocnode.children:
            if isinstance(child, nodes.bullet_list):
                blist = child
                break
        else:
            blist = nodes.bullet_list('')
            tocnode += blist

        reference = nodes.reference(
            '', '', internal=True, refuri=docname,
            anchorname="#" + self.get_ref(node), *heading)
        para = addnodes.compact_paragraph('', '', reference)
        item = nodes.list_item('', para)
        # FIXME: find correct location
        blist.append(item)


def setup(app: Sphinx):
    """Register the extension with Sphinx"""
    app.add_lexer('snakemake', SnakemakeLexer())
    app.add_domain(SnakemakeDomain)
    app.add_directive('autosnake', AutoSnakefileDirective)
    app.add_env_collector(DomainTocTreeCollector)
    app.connect('html-collect-pages', collect_pages)
