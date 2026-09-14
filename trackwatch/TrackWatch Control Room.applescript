-- Source for "TrackWatch Control Room.app". Rebuild with:
--   osacompile -o "TrackWatch Control Room.app" "TrackWatch Control Room.applescript"
-- Just runs the .command launcher that lives next to this app, so all the
-- real logic (repo detection, port check, starting the server, opening
-- the browser) stays in one place: TrackWatch Control Room.command

on run
	set appPosix to POSIX path of (path to me)
	set folderPosix to do shell script "dirname " & quoted form of appPosix
	set launcherPath to folderPosix & "/TrackWatch Control Room.command"
	do shell script quoted form of launcherPath
end run
