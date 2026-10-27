import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import ProjectArchiveReview,{ArchiveReviewResult,type ArchiveReview} from './ProjectArchiveReview';
describe('read-only project archive review',()=>{
 it('exposes bounded review without claiming automatic restoration',()=>{
  const html=renderToStaticMarkup(<ProjectArchiveReview/>);
  expect(html).toContain('Choose project ZIP to check');expect(html).toContain('without importing records or starting jobs');expect(html).toContain('128 MiB');
 });
 it('shows the actual saved counts, hash and integrity scope',()=>{
  const result:ArchiveReview={schemaVersion:1,state:'integrity_reviewed',fileName:'reference.zip',archiveSha256:'a'.repeat(64),archiveBytes:100,expandedBytes:1048576,entryCount:3,projectName:'Observed reference',recordCount:2,jobCount:0,verifiedAssetCount:2,crcCheckedFiles:3,scope:'CRC and asset checks only; no scientific qualification.'};
  const html=renderToStaticMarkup(<ArchiveReviewResult result={result}/>);
  expect(html).toContain('2 saved records');expect(html).toContain('2 assets verified');expect(html).toContain(result.archiveSha256);expect(html).toContain('1.00 MiB');expect(html).toContain(result.scope);
 });
});
