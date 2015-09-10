# Rawcopy: low-level directory tree copy

```
Version :  0.2.0
URL     :  http://github.com/sebastien/rawcopy
```

Rawcopy is a tool that copies directory trees while preserving hard links.
Rawcopy is ideal if you're moving backup archives from tools such as
`rsnapshot`, `rdiff` or
such as trees backed up created by tools `rsnapshot`, `rdiff-backup` or Back In Time.

Here is a typical scenario:

1) You have a directory called `/mnt/backups` that contains your backup
   archive:

   ```
   $ cd /mnt/backups
   $ du -sch *
   54G	20111227-164323-320
   42G	20120828-114147-345
   ```

2) You copy this directory to *another filesystem* `/mnt/new-backup`
   using `rsync -aH` (or `cp -a`):

   ```
   $ rsync -aH /mnt/backups /mnt/new-backup
   $ cd /mnt/new-backup
   $ du -sch *
   53G	20111227-164323-320
   78G	20120828-114147-345
   ```

3) You notice that`20120828-114147-345` directory has almost doubled in size, because some
   of its files are hard-links to content from `20111227-164323-320`, but are
   not detected and copied as new files. As a result, instead of sharing the same
   inode, this results in new files, and a lot of wasted space. A 1Tb backup might
   end up being 10Tb of more without preserving hard links.

However, using `rawcopy will give you the following result`

```
$ rawcopy /mnt/backups -o /mnt/new-backups
$ cd /mnt/new-backup
$ du -sch *
54G	20111227-164323-320
42G	20120828-114147-345
```

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

# Requirements

- Unix system (tested on Ubuntu Linux)
- Python 3

# Install

Rawcopy requires `python3` (tested on python-3.4) and can be easily installed
through a variety of ways:

- Using *pip*: `pip install -U --user rawcopy`
- Using *easy_install*: `easy_install -U rawcopy`
- Using *curl*: `curl https://raw.githubusercontent.com/sebastien/rawcopy/master/rawcopy > rawcopy ; chmod +x rawcopy`

# Usage

Rawcopy is available both as a Python module (`import rawcopy`) and a command
line tool (`rawcopy`).

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

## Copying multiple directories

If you would like to create a copy of `/mnt/old-drive/backup-john"
and `/mnt/old-drive/backup-jane` to `/mnt/new-drive/backup-john`
and `/mnt/new-drive/backup-jane`, you can do:

```
rawcopy -o /mnt/new-drive/ /mnt/old-drive/backup-john /mnt/old-drive/backup-jane
```

Rawcopy will automatically identify the *base path* (`/mnt/old-drive/`) and
map it to `mnt/new/drive`.

## Resuming a an interrupted/failed copy

In the case that a `rawcopy` run failed at somepoint, you can resume it
by looking for the last copied file number, usually prefixing the path
in the output log:

```
Copying path 2553338:icon-video.svg
             ^^^^^^^
             PATH ID
```

To resume the command from path `#2553338` simly do:

```
rawcopy -r2553338- -o <OUTPUT PATH> <PATH TO COPY>...
```

Note that the trailing `-` is important as otherwise only that specific
file will be copied.

## Updating a previously rawcopy'ed directory

Imaging that you've already rawcopy'ed `/mnt/a` to `/mnt/b`, but since then
`/mnt/a` has changed and you would like to update `/mnt/b` accordingly, without
having to redo the full copy.

The first step is to re-generate the catalogue with the `-C` option. This ensures
that all the files in `/mnt/a`, including the new files, are known to `rawcopy`:

```
$ rawcopy -C /mnt/a -o /mnt/b
```

This will update the catalogue stored in `/mnt/b/__rawcopy__` even if it
already exists. Once this is done, you can start/resume the copy as usual:

```
$ rawcopy /mnt/a -o /mnt/b
```

Acknowledgments
---------------

I would like to thank [Jeremy Zawodny](http://jeremy.zawodny.com/) for
[sharing his experience](http://jeremy.zawodny.com/blog/archives/010037.html)
with the suprisingly hard problem of copy directory trees with hard links.