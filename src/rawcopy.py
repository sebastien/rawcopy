#!/usr/bin/env python3
# encoding=utf8 ---------------------------------------------------------------
# Project           : NAME
# -----------------------------------------------------------------------------
# Author            : FFunction
# License           : BSD License
# -----------------------------------------------------------------------------
# Creation date     : 2015-07-27
# Last modification : 2015-07-29
# -----------------------------------------------------------------------------

import os, stat, sys, dbm, argparse, shutil

try:
	import reporter as logging
except:
	import logging

__version__  = "0.1.0"
LICENSE      = "http://ffctn.com/doc/licenses/bsd"
TYPE_BASE    = "B"
TYPE_ROOT    = "R"
TYPE_DIR     = "D"
TYPE_FILE    = "F"
TYPE_SYMLINK = "S"

"""{{{
\# Rawcopy: low-level directory tree copy

```
Version :  0.0.1
URL     :  http://github.com/sebastien/rawcopy
```

Rawcopy is a tool that allows to *copy directory trees that make heavy use of hard links*,
such as trees backed up created by tools `rsnapshot`, `rdiff-backup` or Back In Time.

Here is a typical scenario where you have two incremental backups source trees
to copy:

```
$ du -sch *
54G	20111227-164323-320
42G	20120828-114147-345
```

copying these using `rsync -aH` (or `cp -a`) gave me the following result (note
that the slight size difference might be related to the fact that both
trees are on different filesystems):

```
$ du -sch *
53G	20111227-164323-320
78G	20120828-114147-345
```

The `20120828-114147-345` directory has almost doubled in size, because some of
its files are hard-links to content from `20111227-164323-320`. As these linked
are not detected, they are copied as new files instead of sharing the same
inode. A 1Tb backup might end up being 10Tb of more without preserving hard
links.

now, using `rawcopy`, I got the following:

```
$ du -sch *
53G	20111227-164323-320
42G	20120828-114147-345
```

Features
--------

Raw copy key features are:

- preserves hard-links
- filesystem-agnostic
- copies regular/special/extra attributes (on Linux)
- can be safely interrupted and resumed
- copying can be done incrementally

Rawcopy works by first creating a *catalogue of all the files in the source trees*
and saving it to the output directory (as `__rawcopy__/catalogue.lst`). Then,
rawcopy will use this list to copy the files from the source tree, keeping a
map of original source tree inodes to paths in the destination output
(as `__rawcopy__/copy.db`), allowing for the re-creation of hard-links
in the output directory.

Note that the catalogue and the inodes database take some space. For a ~1Tb data,
you can expect a 500Mb catalogue and a 450Mb for the inode database. Basically,
make sure that you'll have a couple of Gb available in addition to the size
of the source tree.

Install
-------

Rawcopy requires `python3` (tested on python-3.4) and can be easily installed
through a variety of ways:

Using `pip`
:	`pip install -U rawcopy`

Using `easy_install`
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

# NOTE: os.path.exists() fails when symlink has unreachable target
# TODO: Implement fast resume from catalogue (skip ahead to find the last index
# -- or simply store the last offset).
# TODO: Allow to use kyoto cabinet, which should be faster
# TODO: Implement resuming of catalogue
# TODO: Implement a dedup pass that goes over the catalogue and de-duplicates
# everything creating hard links for existing file signatures (and guarding
# against possible collisions)
# TODO: Implement catalogue checking (size,content=md5/sha,attrs)
# FIXME: Right now only hardlinks for files are supported

# NOTE: Better logging
#
# <OP> <TYPE> <PATH> = File unchanged
# OP = ...  = skipping
#      +++  = addding
#      -->  = linking
#      ___  = storing in DB
#      ERR  = error
# TYPE = DIR
#        FIL
#        LNK

def utf8(s):
	return s.encode("utf8", "replace").decode("utf8")

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
			mode = os.lstat(p)[stat.ST_MODE]
			if stat.S_ISCHR(mode):
				logging.info("Catalogue: Skipping special device file: {0}".format(utf8(p)))
			elif stat.S_ISBLK(mode):
				logging.info("Catalogue: Skipping block device file: {0}".format(utf8(p)))
			elif stat.S_ISFIFO(mode):
				logging.info("Catalogue: Skipping FIFO file: {0}".format(utf8(p)))
			elif stat.S_ISSOCK(mode):
				logging.info("Catalogue: Skipping socket file: {0}".format(utf8(p)))
			elif os.path.isfile(p):
				yield (counter, TYPE_ROOT, os.path.dirname(p))
				counter += 1
				yield (counter, TYPE_FILE, os.path.basename(p))
			elif os.path.islink(p):
				yield (counter, TYPE_ROOT, os.path.dirname(p))
				counter += 1
				yield (counter, TYPE_SYMLINK, os.path.basename(p))
			else:
				for root, dirs, files in os.walk(p, topdown=True):
					logging.info("Catalogue: {0} files {1} dirs in {2}".format(len(files), len(dirs), utf8(root)))
					yield (counter, TYPE_ROOT, root)
					for name in files:
						yield (counter, TYPE_SYMLINK if os.path.islink(os.path.join(root, name)) else TYPE_FILE, name)
						counter += 1
					for name in dirs:
						yield (counter, TYPE_DIR, name)
						counter += 1

	def write( self, output ):
		for i, t, p in self.walk():
			try:
				line = bytes("{0}:{1}:{2}\n".format(i,t,p), "utf8")
				output.write(line)
			except UnicodeEncodeError as e:
				logging.error("Catalogue: exception occured {0}".format(e))

	def save( self, path ):
		d = os.path.dirname(path)
		if not os.path.exists(d):
			logging.info("Catalogue: creating catalogue directory {0}".format(utf8(d)))
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

	def fromCatalogue( self, path, range=None, test=False ):
		"""Reads the given catalogue and copies directories, symlinks and files
		listed in the catalogue. Note that this expects the catalogue to
		be in traversal order."""
		logging.info("Opening catalogue: {0}".format(path))
		# The base is the common prefix/ancestor of all the paths in the
		# catalogue. The root changes but will always start with the base.
		base      = None
		root      = None
		self.test = test
		with open(path, "r") as f:
			for line in f:
				j, t, p   = line.split(":", 2) ; p = p[:-1]
				i         = int(j) ; self.last = i

				if t == TYPE_BASE:
					# The first line of the catalogue is expected to be the base
					# it is also expected to be absolute.
					self.base = base = p
					assert os.path.exists(p), "Base directory does not exists: {0}".format(utf8(p))
					# Once we have the base, we can create rawcopy's DB files
					rd = os.path.join(self.output, "__rawcopy__")
					if not os.path.exists(rd):
						logging.info("Copy: creating rawcopy database directory {0}".format(utf8(rd)))
						os.makedirs(rd)
					self._open(os.path.join(rd, "copy.db"))
				elif t == TYPE_ROOT:
					# If we found a root, we ensure that it is prefixed with the
					# base
					assert base, "Catalogue must have a base directory before having roots"
					assert p.startswith(base), "Catalogue roots must be prefixed by the base, base={0}, root={1}".format(utf8(base), utf8(p))
					# Now we extract the suffix, which is the root minus the base
					# and no leading /
					self.root = root = p
					source    = p
					suffix    = p[len(self.base):]
					if suffix[0] == "/": suffix = suffix[1:]
					destination = os.path.join(os.path.join(self.output, suffix))
					if not (os.path.exists(destination) and not os.path.islink(destination)):
						pd = os.path.dirname(destination)
						logging.info("Creating root: {0}:{1}".format(i, utf8(p)))
						# We make sure the source exists
						if not os.path.exists(source) and not os.path.islink(source):
							logging.info("Root does not exists: {0}:{1}".format(i, utf8(p)))
						# We make sure the parent destination exists (it should be the case)
						if not os.path.exists(pd):
							os.makedirs(pd)
						if os.path.isdir(source):
							self.copydir(p, destination, suffix)
						elif self.hardlink(p, destination):
							# NOTE: Hard-linking of directory is NOT permitted
							# Now we see if the file should be a hard link, in which
							# case we do it, otherwise we copy the rest.
							pass
						elif os.path.islink(source):
							self.copylink(p, destination, suffix)
						elif os.path.isfile(source):
							self.copyfile(p, destination, suffix)
						else:
							logging.error("Unsupported root (not a dir/link/file): {0}:{1}".format(i, utf8(p)))
				else:
					# We skip the indexes that are not within the range, if given
					if range:
						if i < range[0]: continue
						if len(range) > 1 and range[1] >= 0 and i > range[1]:
							logging.info("Reached end of range {0} >= {1}".format(i, range[1]))
							break
					assert root and self.output
					# We prepare the source, suffix and destination
					source = os.path.join(root, p)
					assert source.startswith(base), "os.path.join(root={0}, path={1}) expected to start with base={2}".format(repr(root), repr(p), repr(base))
					suffix = source[len(base):]
					if suffix[0] == "/": suffix = suffix[1:]
					destination = os.path.join(os.path.join(self.output, suffix))
					assert suffix, "Empty suffix: source={0}, path={1}, destination={2}".format(utf8(source), utf(p), utf8(destination))
					# We now proceed with the actual copy
					if not (os.path.exists(source) or os.path.islink(source)):
						logging.error("Source path not available: {0}:{1}".format(i,utf8(source)))
					elif not (os.path.exists(destination) or os.path.islink(destination)):
						logging.info("Copy: copying path {0}:{1}".format(i,utf8(p)))
						if t == TYPE_DIR:
							self.copydir(source, destination, p)
						elif self.hardlink(source, destination):
							# NOTE: Hardlinks are not OK in directories
							logging.info("Source was a hardlink: {0}:{1}".format(i,utf8(p)))
						elif t == TYPE_SYMLINK:
							self.copylink(source, destination, p)
						elif t == TYPE_FILE:
							assert root
							self.copyfile(source, destination, p)
						else:
							logging.error("Unsupported catalogue type: {1} at {0}:{1}:{2}", i, t, p)
					else:
						if t == TYPE_DIR:
							logging.info("Skipping already copied directory: {0}:{1}".format(i, utf8(destination)))
						elif t == TYPE_SYMLINK:
							logging.info("Skipping already copied link: {0}:{1}".format(i, utf8(destination)))
						elif t == TYPE_FILE:
							logging.info("Skipping already copied file: {0}:{1}".format(i, utf8(destination)))
						# TODO: We should repair a damaged DB and make sure the inode is copied
						self.ensureInodePath(source, suffix)
				# We sync the database every 1000 item
				if j.endswith("000") and (not range or i>=range[0]):
					logging.info("{0} items processed, syncing db".format(i))
					if hasattr(self.db, "sync"):
						self.db.sync()
		# We don't forget to close the DB
		self._close()

	def copyattr( self, source, destination, stats=None ):
		"""Copies the attributes from source to destination, (re)using the
		given `stats` info if provided."""
		if self.test: return False
		s_stat = stats or os.lstat(source)
		shutil.copystat(source, destination, follow_symlinks=False)
		os.chown(destination, s_stat[stat.ST_GID], s_stat[stat.ST_UID], follow_symlinks=False)

	def copydir( self, source, destination, path ):
		"""Copies the given directory to the destination. This does not
		copy its contents."""
		logging.info("Copying directory: {0}".format(destination))
		if self.test: return False
		os.mkdir(destination)
		self.copyattr(source, destination)

	def copylink( self, source, destination, path ):
		"""Copies the given symlink to the destination. This preserves the
		target but does not check if it is valid or not."""
		target = os.readlink(source)
		logging.info("Copying link [->{1}]: {0}".format(destination, target))
		if self.test: return False
		d      = os.path.dirname(destination)
		f      = os.path.basename(destination)
		os.symlink(target, destination)
		self.copyattr(source, destination)

	def copyfile( self, source, destination, path ):
		"""Copies the given file. This will check the file's inode to
		detect hardlink. If a file with the same inode has already been
		copied, then a hard link will be created to that file, otherwise
		a new file will be created."""
		s_stat  = os.lstat(source)
		mode    = s_stat[stat.ST_MODE]
		if stat.S_ISCHR(mode):
			logging.info("Copy: skipping special device file: {0}".format(utf8(source)))
		elif stat.S_ISBLK(mode):
			logging.info("Copy: skipping block device file: {0}".format(utf8(source)))
		elif stat.S_ISFIFO(mode):
			logging.info("Skipping FIFO file: {0}".format(utf8(source)))
		elif stat.S_ISSOCK(mode):
			logging.info("Skipping socket file: {0}".format(utf8(source)))
		else:
			s_inode = s_stat[stat.ST_INO]
			# If the destination does not exists, then we need to restore
			# it.
			original_path = self.getInodePath(s_inode)
			assert not original_path, "File should be a hard-link: {0}".format(utf8(destination))
			logging.info("Copying file: {0}".format(destination))
			if self.test: return False
			# If we haven't copied the source inode anywhere into the
			# destination, then we copy it, preserving its attributes
			shutil.copyfile(source, destination, follow_symlinks=False)
			# NOTE: We really don't want to have absolute paths here, we
			# need them relative, otherwise the DB is going to explode in
			# size.
			self.setInodePath(s_inode, destination[len(self.output):])
			# In all cases we copy the attributes
			self.copyattr(source, destination)

	def hardlink( self, source, destination ):
		"""Copies the file/directory as a hard link. Return True if
		a hard link was detected."""
		if self.test: return False
		# Otherwise if the inode is already there, then we can
		# simply hardlink it
		s     = os.lstat(source)
		inode = s[stat.ST_INO]
		mode  = s[stat.ST_MODE]
		if stat.S_ISDIR(mode) or os.path.exists(destination):
			# Directories can't have hard links
			return False
		original_path = self.getInodePath(inode)
		if original_path:
			logging.info("Hard linking file: {0}".format(destination))
			link_source = os.path.join(self.base, original_path)
			os.link(link_source, destination, follow_symlinks=False)
			self.copyattr(source, destination)
			return True
		else:
			return False

	def getInodePath( self, inode ):
		path = self.db.get("@" + str(inode))
		return os.path.join(self.output, path.decode("utf8")) if path else None

	def setInodePath( self, inode, path ):
		if path[0] == "/": path = path[1:]
		self.db["@" + str(inode)] = bytes(path, "utf8")

	def ensureInodePath( self, source, path):
		"""Ensures the the given source element path's inode is mapped to the
		given destination's path inode."""
		s     = os.lstat(source)
		inode = s[stat.ST_INO]
		mode  = s[stat.ST_MODE]
		if not stat.S_ISDIR(mode) and not self.getInodePath(inode):
			logging.info("Copy: remapping inode for {0} to {1}".format(utf8(source), utf8(path)))
			self.setInodePath(inode, path)
			return True
		else:
			return False

# -----------------------------------------------------------------------------
#
# SECTION
#
# -----------------------------------------------------------------------------

def run( args ):
	sources = [os.path.abspath(_) for _ in args.source]
	base    = os.path.commonprefix(sources)
	if not os.path.exists(base) or not os.path.isdir(base): base = os.path.dirname(base)
	for s in sources:
		if not os.path.exists(s):
			logging.error("Source path does not exists: {0}".format(s))
			return None
	# We log the information about the sources
	logging.info("Using base: {0}".format(base))
	for _ in sources: logging.info("Using source: {0}".format(_))
	# Sometimes the sources have a common filename prefix, so make sure it is
	# a directory or we get its dirname
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
		r = args.range
		if r:
			try:
				r = [int(_ or -1) for _ in r.split("-")]
			except ValueError as e:
				logging.error("Unsupported range format. Expects `start-end`")
				return -1
			logging.info("Using catalogue item range: {0}".format(r))
		if args.test:
			logging.info("Test mode enabled (not actual file copy)".format(r))
		c.fromCatalogue(cat_path, range=r, test=args.test)

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
	parser.add_argument("-r", "--range", type=str,
		help="The range of elements (by index) to copy from the catalogue"
	)
	parser.add_argument("-t", "--test", action="store_true", default=False,
		help="Does a test run (no actual copy/creation of files)"
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
