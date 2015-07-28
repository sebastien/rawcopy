# Rawcopy
# Perfect-copy for Unix

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