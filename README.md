## Nintendo SARC archive reader and writer

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

### License

This software is licensed under the terms of the GNU General Public License, version 2 or later.
