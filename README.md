# Rawcopy: low-level directory tree copy

```
Version :  0.1.0
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

# Features

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

# Install

Rawcopy requires `python3` (tested on python-3.4) and can be easily installed
through a variety of ways:

Using pip: `pip install -U --user rawcopy`

Using `easy_install`: `easy_install -U rawcopy`

Using `curl`: `curl https://raw.githubusercontent.com/sebastien/rawcopy/master/rawcopy > rawcopy ; chmod +x rawcopy`

# Usage

Rawcopy is available both as a Python module (`rawcopy`) and a command
line tool (`racopy`).

```
usage: rawcopy [-h] [-c CATALOGUE] [-o OUTPUT] [-r RANGE] [-t] [-C]
                  SOURCE [SOURCE ...]

Creates a raw copy of the given source tree

positional arguments:
  SOURCE                The source tree to backup

optional arguments:
  -h, --help            show this help message and exit
  -c CATALOGUE, --catalogue CATALOGUE
                        Uses the given catalogue for all the files to copy.
  -o OUTPUT, --output OUTPUT
                        The path where the source tree will be backed up.
  -r RANGE, --range RANGE
                        The range of elements (by index) to copy from the
                        catalogue
  -t, --test            Does a test run (no actual copy/creation of files)
  -C, --catalogue-only  Does not do any copying, simple creates the catalogue
```

# Use cases

## Copying a single directory

If you would like to create a copy of `/mnt/old-drive/backup/2010` to
`/mnt/new-drive/backup/2010`, you can do:

```
rawcopy -o /mnt/new-drive/backup/2010 /mnt/old-drive/backup/2010
```

## Copying a multiple directories

If you would like to create a copy of `/mnt/old-drive/backup-john"
and `/mnt/old-drive/backup-jane` to `/mnt/new-drive/backup-john`
and `/mnt/new-drive/backup-jane`, you can do:

```
rawcopy -o /mnt/new-drive/ /mnt/old-drive/backup-john /mnt/old-drive/backup-jane
```

Rawcopy will automatically identify the *base path* (`/mnt/old-drive/`) and
map it to `mnt/new/drive`.



# Copying a  tree from one drive to another
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