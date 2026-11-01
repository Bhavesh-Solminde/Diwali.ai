param([ValidateSet('04','05')][string]$Version = '04')
$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path (Split-Path $PSScriptRoot))
$package = if ($Version -eq '04') { 'Kat0-4(Win)/Kat 0.4' } else { 'Kat-05(Win)/Market Simulation' }
$managed = Join-Path $root "Krafer Agent Trader Sim/$package/MarketSimulation_Data/Managed"
# Metadata/IL inspection only: no constructors or game methods are invoked.
Get-ChildItem $managed -Filter 'Unity*.dll' | ForEach-Object {
    try { [Reflection.Assembly]::LoadFrom($_.FullName) | Out-Null } catch { }
}
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Reflection;
using System.Reflection.Emit;
using System.Text;
public static class ControlIL {
 static Dictionary<short,OpCode> ops = new Dictionary<short,OpCode>();
 static ControlIL() { foreach(var f in typeof(OpCodes).GetFields()) if(f.FieldType==typeof(OpCode)){var op=(OpCode)f.GetValue(null);ops[op.Value]=op;} }
 public static string Read(string file) {
  var a=Assembly.LoadFrom(file); var output=new StringBuilder();
  foreach(var t in a.GetTypes()) foreach(var m in t.GetMethods(BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static|BindingFlags.DeclaredOnly)) {
   var b=m.GetMethodBody()?.GetILAsByteArray(); if(b==null)continue;
   var lines=new StringBuilder(); bool input=false;
   for(int i=0;i<b.Length;) {
    int at=i; short key=b[i++];if(key==254)key=(short)(0xfe00|b[i++]);var op=ops[key]; object val="";int n=0;
    switch(op.OperandType) {
     case OperandType.InlineNone:break;
     case OperandType.ShortInlineI:val=(sbyte)b[i];n=1;break;
     case OperandType.ShortInlineVar:val=b[i];n=1;break;
     case OperandType.InlineVar:val=BitConverter.ToUInt16(b,i);n=2;break;
     case OperandType.InlineI:val=BitConverter.ToInt32(b,i);n=4;break;
     case OperandType.InlineI8:val=BitConverter.ToInt64(b,i);n=8;break;
     case OperandType.ShortInlineR:val=BitConverter.ToSingle(b,i);n=4;break;
     case OperandType.InlineR:val=BitConverter.ToDouble(b,i);n=8;break;
     case OperandType.ShortInlineBrTarget:val=i+1+(sbyte)b[i];n=1;break;
     case OperandType.InlineBrTarget:val=i+4+BitConverter.ToInt32(b,i);n=4;break;
     case OperandType.InlineSwitch:n=4+4*BitConverter.ToInt32(b,i);val="switch";break;
     default:
      n=4;int token=BitConverter.ToInt32(b,i);
      try {if(op.OperandType==OperandType.InlineString)val=m.Module.ResolveString(token);else {var member=m.Module.ResolveMember(token);val=member.DeclaringType+"."+member;}} catch {val="token:"+token;}
      break;
    }
    i+=n;string s=val.ToString();if(s.Contains("UnityEngine.Input.")||s.Contains("EventTrigger")||s.Contains("AddListener"))input=true;
    lines.AppendLine(at.ToString("X4")+" "+op.Name+" "+s);
   }
   if(input || m.Name.StartsWith("On") || m.Name.StartsWith("<Start>"))output.AppendLine("METHOD "+t.FullName+"."+m.Name+"\n"+lines);
  }
  return output.ToString();
 }
}
'@
[ControlIL]::Read((Join-Path $managed 'Assembly-CSharp.dll'))
