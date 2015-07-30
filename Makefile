# FFCTN Python Makefile
# -- Version: 2015-07-23
# -- License: BSD License 
# -- (c) FFunction inc www.ffctn.com
PROJECT         = rawcopy
PROJECT_VERSION = $(shell grep __version__ $(SOURCE_FILES) | head -n1 | cut -d'"' -f2)
DOCUMENTATION   =
SOURCES         = src
LIBRARY         = 
TESTS           = 
SCRIPTS         = bin
RESOURCES       =
DIST            = dist
API             = doc/$(PROJECT)-api.html
PACKAGE         = $(PROJECT)
MODULES         = $(shell find $(SOURCES)/$(PACKAGE) -name "*.py" | cut -d "." -f1 | sed "s|^$(SOURCES)/||g;s|\/|\.|g;s|\.__init__||g" )
MODULES        := rawcopy
SOURCE_FILES    = $(shell find $(SOURCES) -name "*.py")
TEST_FILES      = $(shell find $(TESTS) -name "*.py")
DIST_CONTENT    = $(DOCUMENTATION) $(SOURCES) $(SCRIPTS) $(TESTS) $(RESOURCES) Makefile README.md LICENSE.md setup.py
CHECK_BLACKLIST = 
PYTHON          = PYTHONPATH=$(SOURCES) $(shell which python)
PYTHONHOME      = $(shell $(PYTHON) -c "import sys;print filter(lambda x:x[-13:]=='site-packages',sys.path)[0]")
SDOC            = $(shell which sdoc)
PYCHECKER       = $(shell which pychecker)
CTAGS           = $(shell which ctags)
TEXTO           = $(shell which texto)
CURRENT_ARCHIVE = $(PROJECT)-$(PROJECT_VERSION).tar.gz
# This is the project name as lower case, used in the install rule
project_lower   = $(shell echo $(PROJECT) | tr "A-Z" "a-z")
# The installation prefix, used in the install rule
prefix          = /usr/local

# Rules_______________________________________________________________________

.PHONY: help info preparing-pre clean check dist doc tags todo

help:
	@echo
	@echo " $(PROJECT) development make rules:"
	@echo
	@echo "    prepare - prepares the project, may require editing this file"
	@echo "    check   - executes pychecker"
	@echo "    clean   - cleans up build files"
	@echo "    test    - executes the test suite"
	@echo "    doc     - generates the documentation"
	@echo "    info    - displays project information"
	@echo "    tags    - generates ctags"
	@echo "    todo    - view TODO, FIXMES, etc"
	@echo "    dist    - generates distribution"
	@echo
	@echo "    Look at the makefile for overridable variables."

all: prepare clean check test doc dist
	@echo "Making everything for $(PROJECT)"

info:
	@echo "$(PROJECT)-$(PROJECT_VERSION)"
	@echo "Modules: $(MODULES)"
	@echo Source file lines:
	@wc -l $(SOURCE_FILES)

todo:
	@grep  -R --only-matching "TODO.*$$"  $(SOURCE_FILES)
	@grep  -R --only-matching "FIXME.*$$" $(SOURCE_FILES)

prepare:
	@echo "WARNING : You may required root priviledges to execute this rule."
	@echo "Preparing python for $(PROJECT)"
	ln -snf $(PWD)/$(SOURCES)/$(PACKAGE) $(PYTHONHOME)/$(PACKAGE)
	@echo "Preparing done."

clean:
	@echo "Cleaning $(PROJECT)."
	@find . -name "*.pyc" -or -name "*.sw?" -or -name ".DS_Store" -or -name "*.bak" -or -name "*~" -exec rm '{}' ';'
	@rm -rf $(DOCUMENTATION)/API build dist

check:
	@echo "Checking $(PROJECT) sources :"
ifeq ($(shell basename spam/$(PYCHECKER)),pychecker)
	@$(PYCHECKER) -b $(CHECK_BLACKLIST) $(SOURCE_FILES)
	@echo "Checking $(PROJECT) tests :"
	@$(PYCHECKER) -b $(CHECK_BLACKLIST) $(TEST_FILES)
else
	@echo "You need Pychecker to check $(PROJECT)."
	@echo "See <http://pychecker.sf.net>"
endif
	@echo "done."

test: $(SOURCE_FILES) $(TEST_FILES)
	@echo "Testing $(PROJECT)."
	@$(PYTHON)  -c "from unittest import *;TextTestRunner().run(TestLoader().discover('$(TESTS)', pattern='*.py'))"

dist:
	@echo "Creating archive $(DIST)/$(PROJECT)-$(PROJECT_VERSION).tar.gz"
	@mkdir -p $(DIST)/$(PROJECT)-$(PROJECT_VERSION)
	@cp -r $(DIST_CONTENT) $(DIST)/$(PROJECT)-$(PROJECT_VERSION)
	@make -C $(DIST)/$(PROJECT)-$(PROJECT_VERSION) clean
	@make -C $(DIST)/$(PROJECT)-$(PROJECT_VERSION) doc
	@tar cfz $(DIST)/$(PROJECT)-$(PROJECT_VERSION).tar.gz \
	-C $(DIST) $(PROJECT)-$(PROJECT_VERSION)
	@rm -rf $(DIST)/$(PROJECT)-$(PROJECT_VERSION)

README.md: rawcopy.py
	litterate.py $< > $@

%.html: %.md
	pandoc -o $@ $<

doc: README.md
	@echo "Generating $(PROJECT) documentation"
ifeq ($(shell basename spam/$(SDOC)),sdoc)
	@$(SDOC) -mtexto -cp$(SOURCES) $(MODULES) $(API)
else
	@echo "Sdoc is required to generate $(PROJECT) documentation."
endif

tags:
	@echo "Generating $(PROJECT) tags"
ifeq ($(shell basename spam/$(CTAGS)),ctags)
	@$(CTAGS) -R
else
	@echo "Ctags is required to generate $(PROJECT) tags."
	@echo "Please see <http://ctags.sf.net>"
endif

release:
	python setup.py sdist
	python setup.py register

#EOF

