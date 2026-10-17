import {lazy,Suspense} from 'react';
import {createRoot} from 'react-dom/client';
import './styles.css';
import './tokens.css';
import {useInterface} from './lib/interface';
import './observatory.css';
import './laboratory.css';
import './arcade.css';
import './game.css';
const App=lazy(()=>import('./App'));
const DetachedPanel=lazy(()=>import('./components/DetachedPanel'));
const ArcadeWindow=lazy(()=>import('./arcade/ArcadeWindow'));
const params=new URLSearchParams(location.search);
function InterfaceRoot(){useInterface(true);return <Suspense fallback={<div className="arc-loading">Opening your workspace…</div>}>{params.has('arcade')?<ArcadeWindow/>:params.has('panel')?<DetachedPanel id={params.get('panel')!}/>:<App/>}</Suspense>;}
createRoot(document.getElementById('root')!).render(<InterfaceRoot/>);
