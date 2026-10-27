# ADR-0086: Dredge and RV There Yet? on Calimocho (REQ-132)

Status: Accepted (analysis). The RV fix landed runtime-side; the Dredge quit fix is in progress.
Date: 2026-10-27

## Context

The owner asked to analyse, research, document and implement why two
Xbox PC titles stop before gameplay on Calimocho 0.1120.4.6 (COR-276,
COR-277):

- RV There Yet? (Unreal Engine 5, WinGDK) quit by itself about 25 s
  after start, with `FPlatformMisc::RequestExit(0,
  FEngineLoop::PreInitPreStartupScreen.CommandLineCommands)` in its log.
- Dredge (Unity 2021.3, Mono) seemed to stall about 30 s in, and it
  ignored `WM_CLOSE`.

Earlier traces (L12) showed a "Feature 18" query just before RV's
shutdown. Epic's WinGDK platform code is not public, and both game
executables are encrypted at rest, so the evidence had to come from
runtime traces. Dredge's managed assemblies are plain IL and were
decompiled locally for analysis only (COR-266; nothing redistributed).

## Findings

### RV There Yet?

- "Feature 18" is `XGameRuntimeFeature_XUser` (the enum order in the
  runtime's `xgameruntimefeature.idl`). The runtime answers "available",
  and the query comes after the exit decision, so it is not the cause.
- A Wine relay trace limited to calls made by
  `Ride-WinGDK-Shipping.exe` (`RelayFromInclude`, with the C runtime
  excluded) shows the decision on the game thread:
  1. `GameChat2.dll` calls `RoInitialize(RO_INIT_MULTITHREADED)` and
     gets `S_FALSE`: the thread is already in the MTA.
  2. UE calls `VerifyVersionInfoW`, `GetModuleFileNameW`, then
     `CoInitializeEx(NULL, COINIT_APARTMENTTHREADED)`, which returns
     `0x80010106` (`RPC_E_CHANGED_MODE`).
  3. One millisecond later UE calls `PostQuitMessage(0)`, which is how
     `FWindowsPlatformMisc::RequestExit` ends the engine loop.
- The game thread was put into the MTA by our XGameRuntime
  implementation. `InitializeApiImplEx2` calls
  `CoInitializeEx(nullptr, COINIT_MULTITHREADED)` on the caller's thread.
  The Windows runtime doesn't change the caller's apartment.
- Proof: with the runtime's existing diagnostic switch
  `XODUS_PRIVATE_CALLER_OWNS_COM=1` (no COM initialisation on the
  caller's thread), RV passes PreInit, loads `Frontend_Jungle`, logs
  "Engine is initialized" and renders "Press any button to continue".

Other Wine distributions fail earlier, at `GetCurrentPackageInfo`, which
Calimocho already answers.

### Dredge

- Decompiled `GDKPCEntitlementStrategy.Init` ends exactly at
  `XPackageRegisterPackageInstalled`, which matches the last runtime
  call in the trace. Every wait in the GDK console code yields a frame
  (`await Awaiters.NextFrame`), so none of them can spin a thread.
- A managed-stack snapshot at 46 s (`tools/monodump`, below) showed the
  main thread in a Win32 message wait, and the window showed Dredge's
  autosave notice with the "Begin" prompt. The game was waiting for
  input, not stalled. The earlier "spin in JIT code" sample came from
  the loading phase.
- `WM_CLOSE` is still ignored. A managed stack and winedbg backtraces
  taken six seconds after `WM_CLOSE` show the chain:
  1. Unity runs `InControlManager.OnApplicationQuit` →
     `NativeInputDeviceManager.Destroy` → `InControl.Native.Stop()`,
     and the main thread waits in `incontrolnative.dll` for the
     plugin's input thread.
  2. That input thread is inside Wine's `xinput1_4` first-use set-up
     (`InitOnceExecuteOnce` → `start_update_thread_once`), waiting for
     `start_event`.
  3. XInput's update thread never sets it. It is blocked in its first
     window-system call, `RegisterClassExW` →
     `NtUserRegisterClassExWOW`, on the Unix side.
  Dredge's `GameManager.OnApplicationQuit` (which kills the process) is
  never reached. The Unix-side blocker is not yet identified.

## Decision

1. RV: the fix belongs in the XGameRuntime implementation (L12), not in
   Wine: never initialise COM on the caller's thread. If the runtime
   needs the MTA for its own objects, it uses `CoIncrementMTAUsage`
   (implemented in Wine's combase) or a thread it owns. No Calimocho
   patch is needed, and none is made, because Wine already behaves
   like Windows here. L12 shipped this in the runtime at commit
   `39088c3` (it now uses `CoIncrementMTAUsage`). On a fresh prefix
   without the override, RV reaches "Press any button to continue",
   and the FH6 and EDC checks show no regression.
2. Dredge: there is no start-up defect to fix. The quit defect is a
   Wine deadlock in XInput's update-thread start-up. It is fixed in
   Calimocho (patch 0018) once native stacks identify the blocker.
3. `tools/monodump/` is kept as a diagnostic tool (LGPL, our own
   source). It loads into a running Unity Mono game, copies each
   thread's registers and stack while the thread is briefly suspended,
   and resolves JIT addresses through the game's own Mono exports after
   resuming. It is never part of an engine build, a release recipe or a
   title profile.

## Consequences

- RV There Yet? should reach its title screen from the app once the
  runtime change lands. Gameplay past "Press any button" needs input,
  so it is an owner check.
- Titles that relied on the runtime's caller-thread MTA must be
  re-checked after that change (FH6, Hades, Easy Delivery Co.).
- Tracing recipe for future WinGDK titles: `+relay` with
  `RelayFromInclude=<game exe>` and an exclude list containing
  `ucrtbase.*;msvcp140.*;vcruntime140.*` plus the SRW-lock and
  message-pump calls. RV's whole start-up then fits in 4.5 MB.
