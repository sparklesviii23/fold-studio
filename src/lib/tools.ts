import { Atom, Blend, ChartNoAxesColumnIncreasing, GitCompareArrows, Layers, Orbit, PanelTop, ScanLine, Settings2, Terminal, Waypoints, Search, Boxes, FlaskConical, Microscope, Code2, Wrench } from 'lucide-react';
export const tools = [
 {id:'tools',name:'Scientific Tools',description:'Search installed commands, full parameters, formats and extensions',icon:Search},
 {id:'models',name:'Models',description:'Manage the authoritative scientific scene',icon:Boxes},
 {id:'analysis',name:'Analysis Laboratory',description:'Native measurements and scientific calculations',icon:FlaskConical},
 {id:'editing',name:'Molecular Architect',description:'Native mutations, bonds, hydrogens and model building',icon:Wrench},
 {id:'imaging',name:'Imaging Laboratory',description:'Density maps, native contours and fitting',icon:Microscope},
 {id:'python',name:'Scientific Python',description:'Real ChimeraX Python APIs in a FOLD interface',icon:Code2},
 {id:'appearance',name:'Appearance',description:'Representations, chain visibility and scientific color',icon:Blend},
 {id:'atoms',name:'Atomic Explorer',description:'Atoms, side chains and the Atomic Lens',icon:Atom},
 {id:'confidence',name:'Confidence',description:'Source pLDDT, actual prediction arrays and error matrices',icon:ChartNoAxesColumnIncreasing},
 {id:'interactions',name:'Interactions',description:'Exact atom geometry and neighboring contacts',icon:Waypoints},
 {id:'sequence',name:'Sequence',description:'Sequence atlas and residue selection',icon:ScanLine},
 {id:'compare',name:'Compare',description:'Run native Cα superposition and inspect measured RMSD',icon:GitCompareArrows},
 {id:'simulation',name:'Trajectories',description:'Native coordinate-set controls and documentation',icon:Orbit},
 {id:'console',name:'Molecular Console',description:'Complete scientific command engine with verified visual receipts',icon:Terminal},
 {id:'workspace',name:'Workspace',description:'Saved scenes, macros, notes and panel arrangements',icon:Layers},
 {id:'settings',name:'Preferences',description:'Glass accessibility and console shortcut',icon:Settings2},
] as const;
export type ToolId=typeof tools[number]['id'];
export const WorkspaceIcon=PanelTop;
