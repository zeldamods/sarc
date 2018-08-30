## Nintendo SARC archive reader and writer

### Setup

Install Python 3.6+ (**64 bit version**) then run `pip install sarc`.

### List files in an archive

    sarc list ARCHIVE

### Extract an archive

    sarc extract ARCHIVE

### Create an archive

    sarc create [--be] FILES_TO_ADD  DEST_SARC

You can give it directories too, in which case the entire directory will be added to the archive
recursively.

Pass `--be` (shorthand: `-b`) if you want `sarc` to use big endian mode (for the Wii U).

An important option is `--base-path`. This option lets you remove parts of the path.
For example, if you pass a path like `Mods/BotW/System/Version.txt`, you will likely want to pass
`--base-path Mods/BotW` to get rid of the leading components.

If only a single directory is passed, the base path is set for you automatically.

So typical usage example:

    sarc create  ~/botw/Bootup/  ~/botw/ModifiedBootup.pack

### Update an archive

    sarc update  FILES_TO_ADD  SARC_TO_MODIFY

This is almost identical to `create`.

By default, `sarc` will keep the endianness of the original archive. You can override this
with `--endian {le,be}` (le for little and be for big endian).

### Delete files from an archive

    sarc delete  FILES_TO_DELETE  SARC_TO_MODIFY

Nothing much to say here. Just keep in mind FILES_TO_DELETE takes archive paths
(those that are printed by `list`).

### Library usage

```python
import sarc

archive = sarc.read_file_and_make_sarc(file)
# or if you already have a buffer
archive = sarc.SARC(archive_bytes)
if archive:
    for file_name in archive.list_files():
        size = archive.get_file_size(file_name)
        data = archive.get_file_data(file_name)

```

To modify an archive:

```python
import sarc

writer = sarc.make_writer_from_sarc(archive)
# or if you're reading from a file
writer = sarc.read_sarc_and_make_writer(file)
# or for a blank archive
writer = sarc.SARCWriter(be=big_endian)

writer.add_file('test.bfevfl', b'file contents')
writer.add_file('another_file.txt', b'file contents')
writer.add_file('test.bfevfl', b'replacing a file')

writer.delete_file('another_file.txt')

writer.write(output_stream)
```

For more information, please look at [sarc.py](sarc/sarc.py).

### License

This software is licensed under the terms of the GNU General Public License, version 2 or later.
