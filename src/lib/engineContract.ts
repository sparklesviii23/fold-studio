/** Typed contract every Living Biology Laboratory engine declares. See docs/LIVING_BIOLOGY_LAB.md. */
export type EvidenceCategory='A'|'B'|'C'|'D'|'E';
export const evidenceCategories:Record<EvidenceCategory,{name:string;meaning:string}>={
 A:{name:'Experimental',meaning:'Measured on real samples; the record carries the source data and protocol identity.'},
 B:{name:'Physics simulation',meaning:'A numerical solution of stated physical equations for an idealised model; accurate only within the model and its validated domain.'},
 C:{name:'AI prediction',meaning:'Output of a trained statistical model (structure, confidence, sequence). Not a measurement; confidence scores are not affinities.'},
 D:{name:'Parameterised hypothesis',meaning:'A model whose parameters are chosen to represent a biological situation that has not been validated for that situation.'},
 E:{name:'Illustrative',meaning:'A drawing or animation of known biology. Shapes, counts and motion are schematic, not computed.'}};
export interface Quantity{value:number;unit:string}
export interface EngineDescriptor{
 id:string;name:string;version:string;
 evidence:EvidenceCategory;
 spatialScale:{min:Quantity;max:Quantity};timeScale:{min:Quantity;max:Quantity};
 numericalMethod:string;equations:string[];
 inputs:{key:string;unit:string;description:string;bounds:[number,number]}[];
 assumptions:string[];validatedDomain:string[];limits:string[];
 benchmarks:{name:string;reference:string;acceptance:string}[];
 uncertainty:string;
}
export interface ResearchRecord<I=unknown,O=unknown>{
 schema:'fold-studio.research-record';schemaVersion:1;
 engine:Pick<EngineDescriptor,'id'|'name'|'version'|'numericalMethod'>;
 evidence:{category:EvidenceCategory;name:string;statement:string};
 created:string;inputs:I;solver:Record<string,unknown>;outputs:O;
 benchmark?:Record<string,unknown>;assumptions:string[];limitations:string[];
 reproducibility:{deterministic:boolean;seed:number|null;runtime:string;contentSha256?:string};
}
