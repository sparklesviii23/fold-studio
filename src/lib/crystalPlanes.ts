import type {UnitCellInspection,Vector3} from './crystalCell';
import {reciprocalLatticeBasis} from './crystalReplication';
export function interplanarSpacing(cell:UnitCellInspection,millerIndices:Vector3){
 if(millerIndices.length!==3||millerIndices.some(value=>!Number.isInteger(value)||Math.abs(value)>1000)||millerIndices.every(value=>value===0))throw Error('Supply three integer Miller indices from −1000 to 1000, with at least one nonzero index.');
 const reciprocalBasis=reciprocalLatticeBasis(cell.latticeVectorsAngstrom);
 const normal=[0,1,2].map(axis=>millerIndices.reduce((sum,value,i)=>sum+value*reciprocalBasis[i][axis],0)) as Vector3;
 const spacing=1/Math.hypot(...normal);
 if(!Number.isFinite(spacing)||spacing<=0)throw Error('Interplanar spacing is outside the numerical calculation range.');
 return {schemaVersion:1,kind:'reported_lattice_interplanar_spacing',millerIndices:[...millerIndices] as Vector3,spacingAngstrom:spacing,reciprocalPlaneNormalInverseAngstrom:normal,reciprocalBasisInverseAngstrom:reciprocalBasis,reciprocalConvention:'Dual basis a*·a = 1 with no 2π factor; d(hkl) = 1 / |h a* + k b* + l c*|.',sourceLatticeVectorsAngstrom:cell.latticeVectorsAngstrom.map(axis=>[...axis]),recordedSourceSha256:cell.recordedSourceSha256,parsedTextSha256:cell.parsedTextSha256,scope:'Nominal geometric spacing for the selected integer planes in the reported lattice basis. No plane-family equivalence, space-group selection rules, systematic absences, diffraction intensities, experimental peaks or uncertainty propagation are inferred. This is a lattice calculation, not a diffraction simulation or structural refinement.'};
}
