using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Windows.Forms;
using Windows.ApplicationModel.DataTransfer;
using Windows.Storage;

internal static class Program
{
    [DllImport("user32.dll")]
    private static extern bool SetForegroundWindow(IntPtr hWnd);

    private static string _filePath;
    private static string _error;
    private static readonly string LogPath = Path.Combine(Path.GetTempPath(), "eureka-share-log.txt");

    private static void Log(string msg)
    {
        try { File.AppendAllText(LogPath, DateTime.Now.ToString("HH:mm:ss.fff") + " " + msg + Environment.NewLine); }
        catch { }
    }

    [STAThread]
    private static int Main(string[] args)
    {
        try { File.WriteAllText(LogPath, ""); } catch { }
        if (args.Length < 1)
        {
            Log("missing args");
            return 2;
        }

        _filePath = Path.GetFullPath(args[0]);
        Log("file=" + _filePath);
        if (!File.Exists(_filePath))
        {
            Log("missing file");
            return 3;
        }

        ApplicationConfiguration.Initialize();

        var form = new Form
        {
            Text = "Eureka",
            ShowInTaskbar = false,
            FormBorderStyle = FormBorderStyle.None,
            ControlBox = false,
            TopMost = true,
            Width = 2,
            Height = 2,
            StartPosition = FormStartPosition.Manual,
            Left = 0,
            Top = 0,
            Opacity = 0.01,
        };

        form.Shown += (_, _) =>
        {
            try
            {
                SetForegroundWindow(form.Handle);
                Application.DoEvents();
                Log("hwnd=" + form.Handle);
                Share(form.Handle, form);
            }
            catch (Exception ex)
            {
                _error = ex.ToString();
                Log("ERR " + _error);
                form.Close();
            }
        };

        Application.Run(form);
        Log("done err=" + (_error ?? ""));
        return string.IsNullOrEmpty(_error) ? 0 : 1;
    }

    private static void Share(IntPtr hwnd, Form form)
    {
        var manager = DataTransferManagerInterop.GetForWindow(hwnd);
        manager.DataRequested += (sender, args) =>
        {
            Log("DataRequested");
            var deferral = args.Request.GetDeferral();
            try
            {
                // Sync: evita race con chiusura UI.
                var file = StorageFile.GetFileFromPathAsync(_filePath).AsTask().GetAwaiter().GetResult();
                args.Request.Data.Properties.Title = file.Name;
                args.Request.Data.Properties.Description = "Export Eureka";
                args.Request.Data.SetStorageItems(new IStorageItem[] { file });
                Log("set ok " + file.Name);
            }
            catch (Exception ex)
            {
                Log("DataRequested ERR " + ex);
                args.Request.FailWithDisplayText(ex.Message);
                _error = ex.Message;
            }
            finally
            {
                deferral.Complete();
            }
        };

        DataTransferManagerInterop.ShowShareUIForWindow(hwnd);
        Log("ShowShareUIForWindow ok");

        // Esci quando l'utente chiude la share UI (processo resta vivo finché serve).
        var exit = new System.Windows.Forms.Timer { Interval = 300000 };
        exit.Tick += (_, _) =>
        {
            exit.Stop();
            Application.Exit();
        };
        exit.Start();
    }
}
