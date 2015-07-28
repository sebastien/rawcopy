#!/usr/bin/env python3
# encoding=utf8 ---------------------------------------------------------------
# Project           : NAME
# -----------------------------------------------------------------------------
# Author            : FFunction
# License           : BSD License
# -----------------------------------------------------------------------------
# Creation date     : 2015-07-27
# Last modification : 2015-07-28
# -----------------------------------------------------------------------------

import os, stat, sys, dbm, argparse, shutil

try:
	import reporter as logging
except:
	import logging

__version__  = "0.0.0"
LICENSE      = "http://ffctn.com/doc/licenses/bsd"
TYPE_BASE    = "B"
TYPE_ROOT    = "R"
TYPE_DIR     = "D"
TYPE_FILE    = "F"
TYPE_SYMLINK = "S"

"""{{{
\# Rawcopy
## Perfect-copy for Unix

```
Version :  0.0.1
URL     :  http://github.com/sebastien/rawcopy
```

Rawcopy is a tool that allows to copy directory trees that make heavy use of hard links,
such as trees backed up created by tools `rsnapshot`, `rdiff-backup` or Back In Time.

Here is a typical scenario, imagine you have two incremental backups source trees
to copy

```
$ du -sch *
54G	20111227-164323-320
42G	20120828-114147-345
```

copying these using `rsync -aH` (or `cp -a`) gave me the following result:

```
$ du -sch *
53G	20111227-164323-320
78G	20120828-114147-345
```

The `20120828-114147-345` directory has almost doubled in size, because some
of its files are hard-links to content from `20111227-164323-320`, but are
not detected and copied as new files. As a result, instead of sharing the same
inode, this results in new files, and a lot of wasted space. A 1Tb backup might
end up being 10Tb of more without preserving hard links.

Features
--------

Raw copy key features are:

- preserves hard-links
- filesystem-agnostic
- copies regular/special/extra attributes (on Linux)
- can be safely interrupted and resumed
- copying can be done incrementally

Rawcopy works by first creating a catalogue of all the files in the source trees
and saving it to the output directory (as `__rawcopy__/catalogue.lst`). Then,
rawcopy will use this list to copy the files from the source tree, keeping a
map of original source tree inodes to paths in the destination output. This allows
to re-create hard-links on the output directory.

Install
-------

Rawcopy requires `python3` (tested on python-3.4) and can be easily installed
through a variety of ways:

Using pip

:	`pip install -U --user rawcopy`

Using `easy_install`::

:	`easy_install -U rawcopy`

Using `curl`

:	`curl https://raw.githubusercontent.com/sebastien/rawcopy/master/rawcopy > rawcopy ; chmod +x rawcopy`

Use cases
---------

Copying a  tree from one drive to another
===============================================

- moving a backup directory from one drive to another drive, possibly
  with different filesystems
- moving a directory tree that makes a heavy use of hard links
- incrementally copy large amounts of files (1M+ files, 1TB+)

Acknowledgments
---------------

I would like to thank [Jeremy Zawodny](http://jeremy.zawodny.com/) for
[sharing his experience](http://jeremy.zawodny.com/blog/archives/010037.html)
with the suprisingly hard problem of copy directory trees with hard links.

}}}
"""

# -----------------------------------------------------------------------------
#
# CATALOGUE
#
# -----------------------------------------------------------------------------

class Catalogue(object):

	EXCLUDE = "data/wpi/"

	def __init__( self, base, paths=() ):
		self.base  = base
		self.paths = [_ for _ in paths]

	def walk( self ):
		counter = 0
		yield (counter, TYPE_BASE, self.base)
		for p in self.paths:
			for root, dirs, files in os.walk(p, topdown=True):
				logging.info("Catalogue: {0} files {1} dirs in {2}".format(len(files), len(dirs), root))
				yield (counter, TYPE_ROOT, root)
				for name in files:
					yield (counter, TYPE_SYMLINK if os.path.islink(os.path.join(root, name)) else TYPE_FILE, name)
					counter += 1
				for name in dirs:
					yield (counter, TYPE_DIR, name)
					counter += 1

	def write( self, output ):
		for i, t, p in self.walk():
			output.write(bytes("{0}:{1}:{2}\n".format(i,t,p), "utf8"))

	def save( self, path ):
		d = os.path.dirname(path)
		if not os.path.exists(d):
			logging.info("Catalogue: creating catalogue directory {0}".format(d))
			os.makedirs(d)
		with open(path, "wb") as f:
			self.write(f)

# -----------------------------------------------------------------------------
#
# COPY
#
# -----------------------------------------------------------------------------

class Copy(object):

	def __init__( self, output ):
		self.db     = None
		self.last   = -1
		self.output = output
		self.base   = None
		self.root   = None
		if not os.path.exists(output):
			logging.info("Copy: creating output directory {0}".format(output))
			os.makedirs(output)

	def _open( self, path ):
		self._close()
		if not self.db:
			logging.info("Copy: opening copy database at {0}".format(path))
			self.db = dbm.open(path, "c")
		return self

	def _close( self ):
		if self.db:
			logging.info("Copy: opening closing database")
			self.db.close()
			self.db = None
		return self

	def fromCatalogue( self, path ):
		"""Reads the given catalogue and copies directories, symlinks and files
		listed in the catalogue. Note that this expects the catalogue to
		be in traversal order."""
		logging.info("Opening catalogue: {0}".format(path))
		base = None
		root = None
		with open(path, "r") as f:
			for line in f:
				i, t, p   = line.split(":", 2)
				# The path has a trailing '\n'
				p = p[:-1]
				self.last   = int(i)
				source      = os.path.join(root or self.base, p)
				suffix      = source[len(self.base):] if self.base else source
				if suffix[0] == "/": suffix = suffix[1:]
				if not os.path.exists(source):
					logging.error("Source path not available: {0}".format(source))
				elif t == TYPE_BASE:
					self.base = base = p
					assert os.path.exists(p), "Source directory does not exists: {0}".format(p)
					rd = os.path.join(self.output, "__rawcopy__")
					if not os.path.exists(rd): os.makedirs(rd)
					self._open(os.path.join(rd, "copy.db"))
				elif t == TYPE_ROOT:
					self.root   = root = p
					destination = os.path.join(os.path.join(self.output, suffix))
					if not os.path.exists(destination):
						self.copydir(p, destination, suffix)
				else:
					assert root and self.output
					destination = os.path.join(os.path.join(self.output, suffix))
					if not os.path.exists(destination):
						if t == TYPE_DIR:
							self.copydir(source, destination, p)
						elif t == TYPE_SYMLINK:
							self.copylink(source, destination, p)
						elif t == TYPE_FILE:
							assert root
							self.copyfile(source, destination, p)
						else:
							logging.error("Unsupported catalogue type: {1} at {0}:{1}:{2}", i, t, p)
				# We sync the database every 1000 item
				if i.endswith("000"):
					logging.info("{0} items processed, syncing db".format(i))
					if hasattr(self.db, "sync"):
						self.db.sync()
		# We don't forget to close the DB
		self._close()

	def copyattr( self, source, destination, stats=None ):
		"""Copies the attributes from source to destination, (re)using the
		given `stats` info if provided."""
		s_stat = stats or os.lstat(source)
		shutil.copystat(source, destination, follow_symlinks=False)
		os.chown(destination, s_stat[stat.ST_GID], s_stat[stat.ST_UID], follow_symlinks=False)

	def copydir( self, source, destination, path ):
		"""Copies the given directory to the destination. This does not
		copy its contents."""
		logging.info("Copying directory: {0}".format(destination))
		os.mkdir(destination)
		self.copyattr(source, destination)

	def copylink( self, source, destination, path ):
		"""Copies the given symlink to the destination. This preserves the
		target but does not check if it is valid or not."""
		target = os.readlink(source)
		logging.info("Copying link [->{1}]: {0}".format(destination, target))
		d      = os.path.dirname(destination)
		f      = os.path.basename(destination)
		os.symlink(target, destination)
		self.copyattr(source, destination)

	def copyfile( self, source, destination, path ):
		"""Copies the given file. This will check the file's inode to
		detect hardlink. If a file with the same inode has already been
		copied, then a hard link will be created to that file, otherwise
		a new file will be created."""
		logging.info("Copying file: {0}".format(destination))
		s_stat  = os.lstat(source)
		s_inode = s_stat[stat.ST_INO]
		# If the destination does not exists, then we need to restore
		# it.
		original_path = self.getInode(s_inode)
		if not original_path:
			# If we haven't copied the source inode anywhere into the
			# destination, then we copy it, preserving its attributes
			shutil.copyfile(source, destination, follow_symlinks=False)
			# NOTE: We really don't want to have absolute paths here, we
			# need them relative, otherwise the DB is going to explode in
			# size.
			self.setInodePath(s_inode, path)
		else:
			# Otherwise if the inode is already there, then we can
			# simply hardlink it
			link_source = os.path.join(self.base, original_path)
			os.link(link_source, destination, follow_symlinks=False)
		# In all cases we copy the attributes
		self.copyattr(source, destination)

	def getInode( self, inode ):
		inode = str(inode)
		return self.db.get(inode)

	def getInodePath( self, inode ):
		return self.db.get("@" + str(inode))

	def setInodePath( self, inode, path ):
		self.db["@" + str(inode)] = path

# -----------------------------------------------------------------------------
#
# SECTION
#
# -----------------------------------------------------------------------------

def run( args ):
	sources = [os.path.abspath(_) for _ in args.source]
	base    = os.path.commonprefix(sources)
	for s in sources:
		if not os.path.exists(s):
			logging.error("Source path does not exists: {0}".format(s))
			return None
	# We log the information about the sources
	logging.info("Using base: {0}".format(base))
	for _ in sources: logging.info("Using source: {0}".format(_))
	# Sometimes the sources have a common filename prefix, so make sure it is
	# a directory or we get its dirname
	if not os.path.exists(base) or not os.path.isdir(base): base = os.path.dirname(base)
	# Now we create the catalogue
	if not (args.catalogue or args.output):
		logging.error("Either catalogue or output directory are required")
		return -1
	# Now we retrieve/create the catalogue
	cat_path = args.catalogue or os.path.join(args.output, "__rawcopy__", "catalogue.lst")
	if not os.path.exists(cat_path):
		logging.info("Creating source catalogue at {0}".format(cat_path))
		c = Catalogue(base, sources)
		c.save(cat_path)
	# Now we iterate over the catalogue
	if args.output:
		logging.info("Copy catalogue's contents to {0}".format(args.output))
		c = Copy(args.output)
		c.fromCatalogue(cat_path)

def command( args ):
	parser = argparse.ArgumentParser(
		description="Creates a raw copy of the given source tree"
	)
	parser.add_argument("source", metavar="SOURCE",  type=str, nargs="+",
		help="The source tree to backup"
	)
	parser.add_argument("-c", "--catalogue", type=str,
		help="Uses the given catalogue for all the files to copy."
	)
	parser.add_argument("-o", "--output", type=str,
		help="The path where the source tree will be backed up."
	)
	parser.add_argument("-C", "--catalogue-only", action="store_true", default=False,
		help="Does not do any copying, simple creates the catalogue"
	)
	args = parser.parse_args()
	run(args)

# rawcopy -l PATH
#	Creates a list of all the files at the given path, stores it as readonly

# rawcopy -l PATH <DEST>
#	Creates a raw copy of all the files in at the given directory


if __name__ == "__main__":
	if hasattr(logging, "install"): logging.install(channel="stderr")
	else: logging.basicConfig(level=logging.DEBUG)
	command(sys.argv[1:])

# EOF - vim: ts=4 sw=4 noet