package pro.kairavpn.check;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;

import java.io.File;
import java.io.FileNotFoundException;
import java.util.regex.Pattern;

/**
 * Hands a finished report to the app it is shared with, by name and nothing
 * else: content://pro.kairavpn.check.reports/vpncheck-2026-10-19_12-30-05.zip.
 * Not exported; an app reads a report only through the grant that comes
 * with a share.
 */
public final class ReportProvider extends ContentProvider {
    // The zips vpncheck-app makes (internal/app/files.go): one per run,
    // named for when it started.
    private static final Pattern NAME = Pattern.compile("vpncheck-[0-9A-Za-z_.-]+\\.zip");

    static Uri uri(Context context, String name) {
        return new Uri.Builder().scheme("content").authority(context.getPackageName() + ".reports").appendPath(name).build();
    }

    /** The report of that name, or null when there is none. */
    static File report(Context context, String name) {
        if (name == null || !NAME.matcher(name).matches()) {
            return null;
        }
        // Where the check writes them: $XDG_CACHE_HOME/vpncheck/reports,
        // with XDG_CACHE_HOME set to the cache folder (MainActivity).
        File file = new File(new File(context.getCacheDir(), "vpncheck/reports"), name);
        return file.isFile() ? file : null;
    }

    @Override
    public boolean onCreate() {
        return true;
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection, String[] selectionArgs, String sortOrder) {
        File file = report(getContext(), uri.getLastPathSegment());
        if (file == null) {
            return null;
        }
        String[] columns = projection != null ? projection : new String[] {OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE};
        Object[] row = new Object[columns.length];
        for (int i = 0; i < columns.length; i++) {
            if (OpenableColumns.DISPLAY_NAME.equals(columns[i])) {
                row[i] = file.getName();
            } else if (OpenableColumns.SIZE.equals(columns[i])) {
                row[i] = file.length();
            }
        }
        MatrixCursor cursor = new MatrixCursor(columns, 1);
        cursor.addRow(row);
        return cursor;
    }

    @Override
    public String getType(Uri uri) {
        return "application/zip";
    }

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        if (!"r".equals(mode)) {
            throw new FileNotFoundException("read only");
        }
        File file = report(getContext(), uri.getLastPathSegment());
        if (file == null) {
            throw new FileNotFoundException(uri.toString());
        }
        return ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        throw new UnsupportedOperationException("read only");
    }

    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) {
        throw new UnsupportedOperationException("read only");
    }

    @Override
    public int update(Uri uri, ContentValues values, String selection, String[] selectionArgs) {
        throw new UnsupportedOperationException("read only");
    }
}
