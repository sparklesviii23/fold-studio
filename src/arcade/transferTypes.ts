export type TransferTarget='architect'|'sequence'|'boltz2'|'colabfold'|'observatory';
export interface Transfer {id:string;target:TransferTarget;revision?:number}
