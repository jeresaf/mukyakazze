import {useEffect} from 'react';

// Only active issue editors register this guard. Backend authorisation remains authoritative.
const leaveEvent='mukyakazze:leave-editorial';
export function canLeaveEditorial():boolean {
 return window.dispatchEvent(new Event(leaveEvent,{cancelable:true}));
}
export function useEditorialLeaveGuard(dirty:boolean,busy:boolean){
 useEffect(()=>{
  function leave(e:Event){
   if(busy){e.preventDefault();return;}
   if(dirty&&!window.confirm('Discard unsaved editorial changes?'))e.preventDefault();
  }
  function unload(e:BeforeUnloadEvent){if(dirty||busy){e.preventDefault();e.returnValue='';}}
  window.addEventListener(leaveEvent,leave);
  if(dirty||busy)window.addEventListener('beforeunload',unload);
  return()=>{window.removeEventListener(leaveEvent,leave);window.removeEventListener('beforeunload',unload);};
 },[dirty,busy]);
}
