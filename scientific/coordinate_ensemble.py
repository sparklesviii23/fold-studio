"""Explicit multi-MODEL PDB coordinate sets; no generated or inferred dynamics."""
import hashlib,math

def inspect(data):
 frames=[];ids=set();current=None;reference=None;identities=set()
 for line in data.decode('utf8').splitlines():
  kind=line[:6].strip()
  if kind=='MODEL':
   if current is not None:raise ValueError('Nested PDB MODEL records are not supported.')
   try:number=int(line[10:14])
   except ValueError:raise ValueError('Each coordinate frame needs an explicit PDB MODEL number.')
   if number<1 or number in ids or (frames and number<=frames[-1]):raise ValueError('Coordinate frame numbers must be positive, unique and strictly increasing.')
   ids.add(number);current={'id':number,'atoms':[]};identities=set()
  elif kind in ('ATOM','HETATM'):
   if current is None:raise ValueError('Every ensemble atom must be inside an explicit MODEL / ENDMDL block.')
   if len(line)<78 or line[16:17].strip():raise ValueError('Coordinate ensembles require explicit elements and resolved alternate locations.')
   try:xyz=[float(line[start:start+8]) for start in (30,38,46)];occupancy=float(line[54:60]);bfactor=float(line[60:66])
   except ValueError:raise ValueError('Each ensemble atom requires coordinates, occupancy and B factor.')
   if not all(math.isfinite(v) for v in xyz+[occupancy,bfactor]):raise ValueError('Coordinate ensemble values must be finite.')
   identity=(kind,line[6:11],line[12:16],line[17:20],line[21:22],line[22:26],line[26:27],line[76:80].strip())
   site=identity[2:7]
   if site in identities:raise ValueError('Duplicate atom identity in a coordinate frame.')
   identities.add(site);current['atoms'].append((identity,occupancy,bfactor))
   if len(current['atoms'])>250000:raise ValueError('Coordinate ensembles support at most 250,000 atoms per frame.')
  elif kind=='ENDMDL':
   if current is None or not current['atoms']:raise ValueError('Empty or unmatched ENDMDL record.')
   if reference is None:reference=current['atoms']
   elif current['atoms']!=reference:raise ValueError('All frames must retain the same ordered atoms, occupancies and B factors. Import differing models as separate structures.')
   frames.append(current['id']);current=None
   if len(frames)>1000:raise ValueError('This coordinate ensemble import supports at most 1,000 frames.')
  elif kind in ('ANISOU','SIGATM','SIGUIJ'):raise ValueError('Per-frame anisotropic or uncertainty records require a separate validated importer.')
 if current is not None:raise ValueError('The final coordinate frame is missing ENDMDL.')
 if len(frames)<2:raise ValueError('A coordinate ensemble needs at least two explicit MODEL frames.')
 return {'schemaVersion':1,'format':'multi-MODEL PDB','frameIds':frames,'atomsPerFrame':len(reference),'sourceSha256':hashlib.sha256(data).hexdigest(),'topology':'identical ordered explicit atoms and static occupancy/B factors','interpretation':'User-supplied coordinate ensemble; no dynamics, time intervals or force field inferred'}
