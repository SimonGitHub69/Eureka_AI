// EurekaShare.exe - apre la maschera Condividi di Windows per un file.
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.WindowsRuntime;
using System.Windows.Forms;
using Windows.ApplicationModel.DataTransfer;
using Windows.Foundation;
using Windows.Storage;

internal static class Program
{
    [ComImport]
    [Guid("3A3DCD6C-3EAB-43DC-BCDE-45671CE800C8")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IDataTransferManagerInterop
    {
        void GetForWindow(
            [In] IntPtr appWindow,
            [In] ref Guid riid,
            [Out] out IntPtr dataTransferManager);
        void ShowShareUIForWindow(IntPtr appWindow);
    }

    [DllImport("user32.dll")]
    private static extern bool SetForegroundWindow(IntPtr hWnd);

    private static string _filePath;
    private static string _error;
    private static string _logPath;

    private static void Log(string msg)
    {
        try
        {
            File.AppendAllText(_logPath, DateTime.Now.ToString("HH:mm:ss.fff") + " " + msg + Environment.NewLine);
        }
        catch { }
    }

    [STAThread]
    private static int Main(string[] args)
    {
        _logPath = Path.Combine(Path.GetTempPath(), "eureka-share-log.txt");
        try { File.WriteAllText(_logPath, ""); } catch { }

        if (args == null || args.Length < 1 || string.IsNullOrWhiteSpace(args[0]))
        {
            Log("missing args");
            return 2;
        }

        _filePath = Path.GetFullPath(args[0]);
        Log("file=" + _filePath);
        if (!File.Exists(_filePath))
        {
            Log("file missing");
            return 3;
        }

        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);

        var form = new Form
        {
            Text = "Eureka Condivisione",
            ShowInTaskbar = false,
            FormBorderStyle = FormBorderStyle.FixedToolWindow,
            ControlBox = false,
            TopMost = true,
            Width = 260,
            Height = 72,
            StartPosition = FormStartPosition.CenterScreen,
            Opacity = 1,
        };
        form.Controls.Add(new Label
        {
            Text = "Apertura Condividi...",
            Dock = DockStyle.Fill,
            TextAlign = System.Drawing.ContentAlignment.MiddleCenter,
        });

        form.Shown += (s, e) =>
        {
            try
            {
                SetForegroundWindow(form.Handle);
                Application.DoEvents();
                Log("hwnd=" + form.Handle);
                Share(form.Handle, form);
                Log("ShowShareUI called");
            }
            catch (Exception ex)
            {
                _error = ex.ToString();
                Log("ERR " + _error);
                form.Close();
            }
        };

        Application.Run(form);
        Log("exit error=" + (_error ?? ""));
        return string.IsNullOrEmpty(_error) ? 0 : 1;
    }

    private static void Share(IntPtr hwnd, Form form)
    {
        object factoryObj = WindowsRuntimeMarshal.GetActivationFactory(typeof(DataTransferManager));
        IntPtr factoryUnk = Marshal.GetIUnknownForObject(factoryObj);
        Guid interopIid = new Guid("3A3DCD6C-3EAB-43DC-BCDE-45671CE800C8");
        IntPtr interopPtr;
        int hr = Marshal.QueryInterface(factoryUnk, ref interopIid, out interopPtr);
        Marshal.Release(factoryUnk);
        if (hr != 0 || interopPtr == IntPtr.Zero)
        {
            throw new InvalidCastException("IDataTransferManagerInterop non disponibile (hr=" + hr + ")");
        }

        var interop = (IDataTransferManagerInterop)Marshal.GetTypedObjectForIUnknown(
            interopPtr, typeof(IDataTransferManagerInterop));
        Marshal.Release(interopPtr);

        Guid dtmIid = new Guid("a5caee9b-8708-49d1-8f36-4c4d6fa7d36c");
        IntPtr dtmPtr;
        interop.GetForWindow(hwnd, ref dtmIid, out dtmPtr);
        if (dtmPtr == IntPtr.Zero)
        {
            throw new InvalidOperationException("GetForWindow ha restituito null");
        }

        var manager = (DataTransferManager)Marshal.GetObjectForIUnknown(dtmPtr);
        Marshal.Release(dtmPtr);

        TypedEventHandler<DataTransferManager, DataRequestedEventArgs> handler =
            (sender, args) =>
            {
                Log("DataRequested");
                var deferral = args.Request.GetDeferral();
                try
                {
                    var file = Await(StorageFile.GetFileFromPathAsync(_filePath));
                    args.Request.Data.Properties.Title = file.Name;
                    args.Request.Data.Properties.Description = "Export Eureka";
                    args.Request.Data.SetStorageItems(new IStorageItem[] { file });
                    Log("storage items set: " + file.Name);
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

        manager.DataRequested += handler;
        interop.ShowShareUIForWindow(hwnd);

        var hideTimer = new Timer { Interval = 500 };
        hideTimer.Tick += (s, e) =>
        {
            hideTimer.Stop();
            try { form.Opacity = 0; form.Hide(); } catch { }
        };
        hideTimer.Start();

        var exitTimer = new Timer { Interval = 180000 };
        exitTimer.Tick += (s, e) =>
        {
            exitTimer.Stop();
            Application.Exit();
        };
        exitTimer.Start();
    }

    private static T Await<T>(IAsyncOperation<T> operation)
    {
        return operation.AsTask().GetAwaiter().GetResult();
    }
}
