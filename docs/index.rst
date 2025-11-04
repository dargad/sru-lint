SRU Lint Documentation
======================

SRU Lint is a static analysis tool for Ubuntu SRU (Stable Release Update) patches 
designed to run in CI environments and generate human-friendly reports. It provides 
automated validation of patch format, changelog entries, Launchpad integration, 
and compliance with Ubuntu development standards.

The tool features a plugin architecture that allows for extensible checks, 
precise error reporting with line/column spans, and multiple output formats 
including console output with code snippets and machine-readable JSON for 
automation pipelines.

For installation instructions, usage examples, and detailed guides, 
see the **User Docs**. For information on contributing, developing plugins, 
and project architecture, see the **Contributor Docs**.

.. toctree::
   :hidden:
   :maxdepth: 2

   Users </user-docs/index>
   Contributors </contrib-docs/index>

In this documentation
---------------------

.. grid:: 1 1 2 2

   .. grid-item-card:: User Docs
      :link: /user-docs/index
      :link-type: doc

      **For users and operators** - how to use and operate SRU Lint.

   .. grid-item-card:: Contributor Docs
      :link: /contrib-docs/index
      :link-type: doc

      **For contributors** - how to contribute to SRU Lint.
