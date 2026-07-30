(function(){const n=document.createElement("link").relList;if(n&&n.supports&&n.supports("modulepreload"))return;for(const l of document.querySelectorAll('link[rel="modulepreload"]'))r(l);new MutationObserver(l=>{for(const i of l)if(i.type==="childList")for(const s of i.addedNodes)s.tagName==="LINK"&&s.rel==="modulepreload"&&r(s)}).observe(document,{childList:!0,subtree:!0});function t(l){const i={};return l.integrity&&(i.integrity=l.integrity),l.referrerPolicy&&(i.referrerPolicy=l.referrerPolicy),l.crossOrigin==="use-credentials"?i.credentials="include":l.crossOrigin==="anonymous"?i.credentials="omit":i.credentials="same-origin",i}function r(l){if(l.ep)return;l.ep=!0;const i=t(l);fetch(l.href,i)}})();function ff(e){return e&&e.__esModule&&Object.prototype.hasOwnProperty.call(e,"default")?e.default:e}var Vu={exports:{}},Cl={},Bu={exports:{}},O={};/**
 * @license React
 * react.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */var wr=Symbol.for("react.element"),df=Symbol.for("react.portal"),pf=Symbol.for("react.fragment"),hf=Symbol.for("react.strict_mode"),mf=Symbol.for("react.profiler"),vf=Symbol.for("react.provider"),gf=Symbol.for("react.context"),yf=Symbol.for("react.forward_ref"),xf=Symbol.for("react.suspense"),wf=Symbol.for("react.memo"),Sf=Symbol.for("react.lazy"),Lo=Symbol.iterator;function kf(e){return e===null||typeof e!="object"?null:(e=Lo&&e[Lo]||e["@@iterator"],typeof e=="function"?e:null)}var Hu={isMounted:function(){return!1},enqueueForceUpdate:function(){},enqueueReplaceState:function(){},enqueueSetState:function(){}},Qu=Object.assign,Wu={};function zt(e,n,t){this.props=e,this.context=n,this.refs=Wu,this.updater=t||Hu}zt.prototype.isReactComponent={};zt.prototype.setState=function(e,n){if(typeof e!="object"&&typeof e!="function"&&e!=null)throw Error("setState(...): takes an object of state variables to update or a function which returns an object of state variables.");this.updater.enqueueSetState(this,e,n,"setState")};zt.prototype.forceUpdate=function(e){this.updater.enqueueForceUpdate(this,e,"forceUpdate")};function Ku(){}Ku.prototype=zt.prototype;function fs(e,n,t){this.props=e,this.context=n,this.refs=Wu,this.updater=t||Hu}var ds=fs.prototype=new Ku;ds.constructor=fs;Qu(ds,zt.prototype);ds.isPureReactComponent=!0;var To=Array.isArray,Gu=Object.prototype.hasOwnProperty,ps={current:null},Yu={key:!0,ref:!0,__self:!0,__source:!0};function Xu(e,n,t){var r,l={},i=null,s=null;if(n!=null)for(r in n.ref!==void 0&&(s=n.ref),n.key!==void 0&&(i=""+n.key),n)Gu.call(n,r)&&!Yu.hasOwnProperty(r)&&(l[r]=n[r]);var o=arguments.length-2;if(o===1)l.children=t;else if(1<o){for(var a=Array(o),f=0;f<o;f++)a[f]=arguments[f+2];l.children=a}if(e&&e.defaultProps)for(r in o=e.defaultProps,o)l[r]===void 0&&(l[r]=o[r]);return{$$typeof:wr,type:e,key:i,ref:s,props:l,_owner:ps.current}}function _f(e,n){return{$$typeof:wr,type:e.type,key:n,ref:e.ref,props:e.props,_owner:e._owner}}function hs(e){return typeof e=="object"&&e!==null&&e.$$typeof===wr}function Nf(e){var n={"=":"=0",":":"=2"};return"$"+e.replace(/[=:]/g,function(t){return n[t]})}var Io=/\/+/g;function Wl(e,n){return typeof e=="object"&&e!==null&&e.key!=null?Nf(""+e.key):n.toString(36)}function Qr(e,n,t,r,l){var i=typeof e;(i==="undefined"||i==="boolean")&&(e=null);var s=!1;if(e===null)s=!0;else switch(i){case"string":case"number":s=!0;break;case"object":switch(e.$$typeof){case wr:case df:s=!0}}if(s)return s=e,l=l(s),e=r===""?"."+Wl(s,0):r,To(l)?(t="",e!=null&&(t=e.replace(Io,"$&/")+"/"),Qr(l,n,t,"",function(f){return f})):l!=null&&(hs(l)&&(l=_f(l,t+(!l.key||s&&s.key===l.key?"":(""+l.key).replace(Io,"$&/")+"/")+e)),n.push(l)),1;if(s=0,r=r===""?".":r+":",To(e))for(var o=0;o<e.length;o++){i=e[o];var a=r+Wl(i,o);s+=Qr(i,n,t,a,l)}else if(a=kf(e),typeof a=="function")for(e=a.call(e),o=0;!(i=e.next()).done;)i=i.value,a=r+Wl(i,o++),s+=Qr(i,n,t,a,l);else if(i==="object")throw n=String(e),Error("Objects are not valid as a React child (found: "+(n==="[object Object]"?"object with keys {"+Object.keys(e).join(", ")+"}":n)+"). If you meant to render a collection of children, use an array instead.");return s}function Er(e,n,t){if(e==null)return e;var r=[],l=0;return Qr(e,r,"","",function(i){return n.call(t,i,l++)}),r}function jf(e){if(e._status===-1){var n=e._result;n=n(),n.then(function(t){(e._status===0||e._status===-1)&&(e._status=1,e._result=t)},function(t){(e._status===0||e._status===-1)&&(e._status=2,e._result=t)}),e._status===-1&&(e._status=0,e._result=n)}if(e._status===1)return e._result.default;throw e._result}var xe={current:null},Wr={transition:null},Cf={ReactCurrentDispatcher:xe,ReactCurrentBatchConfig:Wr,ReactCurrentOwner:ps};function Zu(){throw Error("act(...) is not supported in production builds of React.")}O.Children={map:Er,forEach:function(e,n,t){Er(e,function(){n.apply(this,arguments)},t)},count:function(e){var n=0;return Er(e,function(){n++}),n},toArray:function(e){return Er(e,function(n){return n})||[]},only:function(e){if(!hs(e))throw Error("React.Children.only expected to receive a single React element child.");return e}};O.Component=zt;O.Fragment=pf;O.Profiler=mf;O.PureComponent=fs;O.StrictMode=hf;O.Suspense=xf;O.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED=Cf;O.act=Zu;O.cloneElement=function(e,n,t){if(e==null)throw Error("React.cloneElement(...): The argument must be a React element, but you passed "+e+".");var r=Qu({},e.props),l=e.key,i=e.ref,s=e._owner;if(n!=null){if(n.ref!==void 0&&(i=n.ref,s=ps.current),n.key!==void 0&&(l=""+n.key),e.type&&e.type.defaultProps)var o=e.type.defaultProps;for(a in n)Gu.call(n,a)&&!Yu.hasOwnProperty(a)&&(r[a]=n[a]===void 0&&o!==void 0?o[a]:n[a])}var a=arguments.length-2;if(a===1)r.children=t;else if(1<a){o=Array(a);for(var f=0;f<a;f++)o[f]=arguments[f+2];r.children=o}return{$$typeof:wr,type:e.type,key:l,ref:i,props:r,_owner:s}};O.createContext=function(e){return e={$$typeof:gf,_currentValue:e,_currentValue2:e,_threadCount:0,Provider:null,Consumer:null,_defaultValue:null,_globalName:null},e.Provider={$$typeof:vf,_context:e},e.Consumer=e};O.createElement=Xu;O.createFactory=function(e){var n=Xu.bind(null,e);return n.type=e,n};O.createRef=function(){return{current:null}};O.forwardRef=function(e){return{$$typeof:yf,render:e}};O.isValidElement=hs;O.lazy=function(e){return{$$typeof:Sf,_payload:{_status:-1,_result:e},_init:jf}};O.memo=function(e,n){return{$$typeof:wf,type:e,compare:n===void 0?null:n}};O.startTransition=function(e){var n=Wr.transition;Wr.transition={};try{e()}finally{Wr.transition=n}};O.unstable_act=Zu;O.useCallback=function(e,n){return xe.current.useCallback(e,n)};O.useContext=function(e){return xe.current.useContext(e)};O.useDebugValue=function(){};O.useDeferredValue=function(e){return xe.current.useDeferredValue(e)};O.useEffect=function(e,n){return xe.current.useEffect(e,n)};O.useId=function(){return xe.current.useId()};O.useImperativeHandle=function(e,n,t){return xe.current.useImperativeHandle(e,n,t)};O.useInsertionEffect=function(e,n){return xe.current.useInsertionEffect(e,n)};O.useLayoutEffect=function(e,n){return xe.current.useLayoutEffect(e,n)};O.useMemo=function(e,n){return xe.current.useMemo(e,n)};O.useReducer=function(e,n,t){return xe.current.useReducer(e,n,t)};O.useRef=function(e){return xe.current.useRef(e)};O.useState=function(e){return xe.current.useState(e)};O.useSyncExternalStore=function(e,n,t){return xe.current.useSyncExternalStore(e,n,t)};O.useTransition=function(){return xe.current.useTransition()};O.version="18.3.1";Bu.exports=O;var M=Bu.exports;const Ef=ff(M);/**
 * @license React
 * react-jsx-runtime.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */var Pf=M,zf=Symbol.for("react.element"),Lf=Symbol.for("react.fragment"),Tf=Object.prototype.hasOwnProperty,If=Pf.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentOwner,Rf={key:!0,ref:!0,__self:!0,__source:!0};function Ju(e,n,t){var r,l={},i=null,s=null;t!==void 0&&(i=""+t),n.key!==void 0&&(i=""+n.key),n.ref!==void 0&&(s=n.ref);for(r in n)Tf.call(n,r)&&!Rf.hasOwnProperty(r)&&(l[r]=n[r]);if(e&&e.defaultProps)for(r in n=e.defaultProps,n)l[r]===void 0&&(l[r]=n[r]);return{$$typeof:zf,type:e,key:i,ref:s,props:l,_owner:If.current}}Cl.Fragment=Lf;Cl.jsx=Ju;Cl.jsxs=Ju;Vu.exports=Cl;var u=Vu.exports,qu={exports:{}},Ie={},bu={exports:{}},ea={};/**
 * @license React
 * scheduler.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */(function(e){function n(C,I){var R=C.length;C.push(I);e:for(;0<R;){var G=R-1>>>1,W=C[G];if(0<l(W,I))C[G]=I,C[R]=W,R=G;else break e}}function t(C){return C.length===0?null:C[0]}function r(C){if(C.length===0)return null;var I=C[0],R=C.pop();if(R!==I){C[0]=R;e:for(var G=0,W=C.length,tn=W>>>1;G<tn;){var Ae=2*(G+1)-1,nt=C[Ae],rn=Ae+1,ln=C[rn];if(0>l(nt,R))rn<W&&0>l(ln,nt)?(C[G]=ln,C[rn]=R,G=rn):(C[G]=nt,C[Ae]=R,G=Ae);else if(rn<W&&0>l(ln,R))C[G]=ln,C[rn]=R,G=rn;else break e}}return I}function l(C,I){var R=C.sortIndex-I.sortIndex;return R!==0?R:C.id-I.id}if(typeof performance=="object"&&typeof performance.now=="function"){var i=performance;e.unstable_now=function(){return i.now()}}else{var s=Date,o=s.now();e.unstable_now=function(){return s.now()-o}}var a=[],f=[],v=1,g=null,h=3,k=!1,_=!1,y=!1,U=typeof setTimeout=="function"?setTimeout:null,d=typeof clearTimeout=="function"?clearTimeout:null,c=typeof setImmediate<"u"?setImmediate:null;typeof navigator<"u"&&navigator.scheduling!==void 0&&navigator.scheduling.isInputPending!==void 0&&navigator.scheduling.isInputPending.bind(navigator.scheduling);function p(C){for(var I=t(f);I!==null;){if(I.callback===null)r(f);else if(I.startTime<=C)r(f),I.sortIndex=I.expirationTime,n(a,I);else break;I=t(f)}}function w(C){if(y=!1,p(C),!_)if(t(a)!==null)_=!0,ve(m);else{var I=t(f);I!==null&&et(w,I.startTime-C)}}function m(C,I){_=!1,y&&(y=!1,d(E),E=-1),k=!0;var R=h;try{for(p(I),g=t(a);g!==null&&(!(g.expirationTime>I)||C&&!V());){var G=g.callback;if(typeof G=="function"){g.callback=null,h=g.priorityLevel;var W=G(g.expirationTime<=I);I=e.unstable_now(),typeof W=="function"?g.callback=W:g===t(a)&&r(a),p(I)}else r(a);g=t(a)}if(g!==null)var tn=!0;else{var Ae=t(f);Ae!==null&&et(w,Ae.startTime-I),tn=!1}return tn}finally{g=null,h=R,k=!1}}var N=!1,j=null,E=-1,D=5,T=-1;function V(){return!(e.unstable_now()-T<D)}function se(){if(j!==null){var C=e.unstable_now();T=C;var I=!0;try{I=j(!0,C)}finally{I?Ye():(N=!1,j=null)}}else N=!1}var Ye;if(typeof c=="function")Ye=function(){c(se)};else if(typeof MessageChannel<"u"){var $n=new MessageChannel,Xe=$n.port2;$n.port1.onmessage=se,Ye=function(){Xe.postMessage(null)}}else Ye=function(){U(se,0)};function ve(C){j=C,N||(N=!0,Ye())}function et(C,I){E=U(function(){C(e.unstable_now())},I)}e.unstable_IdlePriority=5,e.unstable_ImmediatePriority=1,e.unstable_LowPriority=4,e.unstable_NormalPriority=3,e.unstable_Profiling=null,e.unstable_UserBlockingPriority=2,e.unstable_cancelCallback=function(C){C.callback=null},e.unstable_continueExecution=function(){_||k||(_=!0,ve(m))},e.unstable_forceFrameRate=function(C){0>C||125<C?console.error("forceFrameRate takes a positive int between 0 and 125, forcing frame rates higher than 125 fps is not supported"):D=0<C?Math.floor(1e3/C):5},e.unstable_getCurrentPriorityLevel=function(){return h},e.unstable_getFirstCallbackNode=function(){return t(a)},e.unstable_next=function(C){switch(h){case 1:case 2:case 3:var I=3;break;default:I=h}var R=h;h=I;try{return C()}finally{h=R}},e.unstable_pauseExecution=function(){},e.unstable_requestPaint=function(){},e.unstable_runWithPriority=function(C,I){switch(C){case 1:case 2:case 3:case 4:case 5:break;default:C=3}var R=h;h=C;try{return I()}finally{h=R}},e.unstable_scheduleCallback=function(C,I,R){var G=e.unstable_now();switch(typeof R=="object"&&R!==null?(R=R.delay,R=typeof R=="number"&&0<R?G+R:G):R=G,C){case 1:var W=-1;break;case 2:W=250;break;case 5:W=1073741823;break;case 4:W=1e4;break;default:W=5e3}return W=R+W,C={id:v++,callback:I,priorityLevel:C,startTime:R,expirationTime:W,sortIndex:-1},R>G?(C.sortIndex=R,n(f,C),t(a)===null&&C===t(f)&&(y?(d(E),E=-1):y=!0,et(w,R-G))):(C.sortIndex=W,n(a,C),_||k||(_=!0,ve(m))),C},e.unstable_shouldYield=V,e.unstable_wrapCallback=function(C){var I=h;return function(){var R=h;h=I;try{return C.apply(this,arguments)}finally{h=R}}}})(ea);bu.exports=ea;var Mf=bu.exports;/**
 * @license React
 * react-dom.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */var Of=M,Te=Mf;function S(e){for(var n="https://reactjs.org/docs/error-decoder.html?invariant="+e,t=1;t<arguments.length;t++)n+="&args[]="+encodeURIComponent(arguments[t]);return"Minified React error #"+e+"; visit "+n+" for the full message or use the non-minified dev environment for full errors and additional helpful warnings."}var na=new Set,rr={};function qn(e,n){kt(e,n),kt(e+"Capture",n)}function kt(e,n){for(rr[e]=n,e=0;e<n.length;e++)na.add(n[e])}var pn=!(typeof window>"u"||typeof window.document>"u"||typeof window.document.createElement>"u"),xi=Object.prototype.hasOwnProperty,Ff=/^[:A-Z_a-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD][:A-Z_a-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\-.0-9\u00B7\u0300-\u036F\u203F-\u2040]*$/,Ro={},Mo={};function Df(e){return xi.call(Mo,e)?!0:xi.call(Ro,e)?!1:Ff.test(e)?Mo[e]=!0:(Ro[e]=!0,!1)}function $f(e,n,t,r){if(t!==null&&t.type===0)return!1;switch(typeof n){case"function":case"symbol":return!0;case"boolean":return r?!1:t!==null?!t.acceptsBooleans:(e=e.toLowerCase().slice(0,5),e!=="data-"&&e!=="aria-");default:return!1}}function Uf(e,n,t,r){if(n===null||typeof n>"u"||$f(e,n,t,r))return!0;if(r)return!1;if(t!==null)switch(t.type){case 3:return!n;case 4:return n===!1;case 5:return isNaN(n);case 6:return isNaN(n)||1>n}return!1}function we(e,n,t,r,l,i,s){this.acceptsBooleans=n===2||n===3||n===4,this.attributeName=r,this.attributeNamespace=l,this.mustUseProperty=t,this.propertyName=e,this.type=n,this.sanitizeURL=i,this.removeEmptyString=s}var fe={};"children dangerouslySetInnerHTML defaultValue defaultChecked innerHTML suppressContentEditableWarning suppressHydrationWarning style".split(" ").forEach(function(e){fe[e]=new we(e,0,!1,e,null,!1,!1)});[["acceptCharset","accept-charset"],["className","class"],["htmlFor","for"],["httpEquiv","http-equiv"]].forEach(function(e){var n=e[0];fe[n]=new we(n,1,!1,e[1],null,!1,!1)});["contentEditable","draggable","spellCheck","value"].forEach(function(e){fe[e]=new we(e,2,!1,e.toLowerCase(),null,!1,!1)});["autoReverse","externalResourcesRequired","focusable","preserveAlpha"].forEach(function(e){fe[e]=new we(e,2,!1,e,null,!1,!1)});"allowFullScreen async autoFocus autoPlay controls default defer disabled disablePictureInPicture disableRemotePlayback formNoValidate hidden loop noModule noValidate open playsInline readOnly required reversed scoped seamless itemScope".split(" ").forEach(function(e){fe[e]=new we(e,3,!1,e.toLowerCase(),null,!1,!1)});["checked","multiple","muted","selected"].forEach(function(e){fe[e]=new we(e,3,!0,e,null,!1,!1)});["capture","download"].forEach(function(e){fe[e]=new we(e,4,!1,e,null,!1,!1)});["cols","rows","size","span"].forEach(function(e){fe[e]=new we(e,6,!1,e,null,!1,!1)});["rowSpan","start"].forEach(function(e){fe[e]=new we(e,5,!1,e.toLowerCase(),null,!1,!1)});var ms=/[\-:]([a-z])/g;function vs(e){return e[1].toUpperCase()}"accent-height alignment-baseline arabic-form baseline-shift cap-height clip-path clip-rule color-interpolation color-interpolation-filters color-profile color-rendering dominant-baseline enable-background fill-opacity fill-rule flood-color flood-opacity font-family font-size font-size-adjust font-stretch font-style font-variant fon@import"https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,500;9..144,700&display=swap";:root{--bg: #f4f7fb;--bg-accent: #e8eef8;--panel: rgba(255, 255, 255, .8);--line: #d7e1f0;--text: #132748;--muted: #667895;--ok: #1f9d67;--run: #2b8cff;--warn: #d98d00;--err: #d1443f;--shadow: 0 22px 50px rgba(32, 56, 97, .14);--shadow-soft: 0 10px 26px rgba(42, 67, 112, .1);--radius-lg: 18px;--radius-md: 14px;--ring: 0 0 0 4px rgba(60, 126, 226, .16)}*{box-sizing:border-box}body{margin:0;font-family:Manrope,Noto Sans SC,sans-serif;color:var(--text);position:relative;overflow-x:hidden;background:radial-gradient(circle at 8% 10%,#ffffff 0 18%,transparent 50%),radial-gradient(circle at 88% 0%,#d7e6ff 0 24%,transparent 52%),radial-gradient(circle at 76% 72%,#fef4de 0 14%,transparent 42%),linear-gradient(165deg,var(--bg) 0%,var(--bg-accent) 100%);min-height:100vh}body:before,body:after{content:"";position:fixed;pointer-events:none;z-index:0;filter:blur(2px)}body:before{width:42vw;height:42vw;max-width:520px;max-height:520px;top:-170px;right:-120px;border-radius:50%;background:radial-gradient(circle,#4988ec38,#4988ec00 70%);animation:drift 14s ease-in-out infinite}body:after{width:34vw;height:34vw;max-width:420px;max-height:420px;bottom:-140px;left:-120px;border-radius:50%;background:radial-gradient(circle,#f7b04f2e,#f7b04f00 70%);animation:drift 18s ease-in-out infinite reverse}h1,h2,h3,h4{margin:0;font-family:Fraunces,"Noto Serif SC",serif;font-weight:600;letter-spacing:.01em}.page{max-width:1480px;margin:0 auto;padding:22px;position:relative;z-index:1}.launcher-page{min-height:100vh;display:grid;place-items:center}.launcher-hero{width:min(900px,100%);padding:28px;animation:fadeUp .5s ease both}.launcher-subtitle{margin-top:8px;color:var(--muted)}.launcher-meta{margin-top:14px;display:flex;gap:8px;flex-wrap:wrap}.launcher-actions{display:flex;gap:10px;margin-top:16px;flex-wrap:wrap}.launcher-tabs{margin-top:12px;display:inline-flex;border:1px solid #cfddf1;border-radius:999px;overflow:hidden;background:#ffffffe0}.launcher-tab{border:0;border-radius:0;background:transparent;color:#5f7392;padding:8px 14px;font-weight:600}.launcher-tab.active{color:#1b5fb6;background:linear-gradient(180deg,#e2f0fff2,#d6e8ffe6)}.primary-btn{background:linear-gradient(120deg,#1d79f0,#2ba4ef);border-color:#1f7dff;color:#fff;box-shadow:0 10px 20px #287dee47}.primary-btn:hover{border-color:#1768d9;transform:translateY(-1px);box-shadow:0 13px 22px #287dee57}.primary-btn:active{transform:translateY(0)}.recent-cases{margin-top:16px;display:grid;grid-template-columns:1fr;gap:10px}.kb-manager{margin-top:14px}.kb-manager-head{display:flex;align-items:center;justify-content:space-between;gap:10px}.kb-manager-subtitle{margin:8px 0 0;color:var(--muted)}.kb-shelves{margin-top:12px;display:grid;gap:12px}.kb-view-tabs{margin-top:12px;display:inline-flex;gap:6px;padding:4px;border:1px solid #d4dfef;border-radius:10px;background:#f1f7ffe6}.kb-view-tab{border:0;border-radius:7px;padding:8px 12px;color:#37506f;background:transparent;cursor:pointer}.kb-view-tab.active{color:#fff;background:#2f88f2}.kg-view{margin-top:12px;display:grid;gap:12px}.kg-toolbar{display:flex;align-items:flex-end;gap:10px;flex-wrap:wrap}.kg-search{display:grid;gap:6px;min-width:min(420px,100%);color:var(--muted);font-size:.86rem}.kg-search input{min-height:38px;border:1px solid #d4dfef;border-radius:8px;padding:0 10px;background:#fff}.kg-stats{display:flex;gap:8px;flex-wrap:wrap}.kg-layout{display:grid;grid-template-columns:minmax(0,1fr) minmax(260px,.34fr);gap:12px;align-items:stretch}.kg-canvas-wrap,.kg-detail{border:1px solid #d4dfef;border-radius:12px;background:#fffffff5;box-shadow:var(--shadow-soft)}.kg-canvas-wrap{min-height:520px;overflow:auto}.kg-canvas{width:100%;min-width:960px;height:620px}.kg-lane line{stroke:#d8e3f2;stroke-width:1;stroke-dasharray:6 8}.kg-lane text{fill:#37506f;font-size:13px;font-weight:800;text-anchor:middle}.kg-edge{stroke:#9eb4d5;stroke-width:1.4;opacity:.58}.kg-edge.active{stroke:#2f88f2;stroke-width:2.3;opacity:.95}.kg-edge.dimmed{opacity:.16}.kg-edge-label{fill:#37506f;font-size:11px;paint-order:stroke;stroke:#fff;stroke-width:4px}.kg-node{cursor:pointer}.kg-node rect{stroke:#fff;stroke-width:1.5;filter:drop-shadow(0 6px 8px rgba(36,64,106,.18))}.kg-node.active rect{stroke:#173a67;stroke-width:3}.kg-node.dimmed{opacity:.32}.kg-node text{fill:#fff;font-size:12px;font-weight:700;dominant-baseline:middle;text-anchor:middle;pointer-events:none}.kg-detail{padding:14px;overflow:auto;max-height:620px}.kg-detail h4,.kg-detail h5{margin:0 0 10px}.kg-detail h5{margin-top:14px;color:#37506f}.kg-detail-meta{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}.kg-snippet,.kg-clinical-meaning,.kg-source-ref{margin:8px 0;color:#4f6685;line-height:1.55}.kg-clinical-meaning{color:#24384f;font-weight:700}.kg-source-ref{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.82rem}.kg-list{margin:0;padding-left:18px;display:grid;gap:8px;color:#314864}.kg-list p{margin:4px 0 0;color:#627693}.kg-list li span{margin-left:6px;color:#627693}@media (max-width: 960px){.kg-layout{grid-template-columns:1fr}.kg-canvas{min-width:860px}}.kb-shelf{border:1px solid #d4dfef;border-radius:14px;padding:12px;background:linear-gradient(180deg,#fffffff5,#f7fbfff0);box-shadow:var(--shadow-soft)}.kb-shelf-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px}.kb-shelf-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px}.kb-book{border:1px solid #d6e2f3;border-radius:12px;background:#fffffff2;display:grid;grid-template-columns:8px 1fr;min-height:146px;overflow:hidden;box-shadow:0 10px 18px #2a43701c;transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease}.kb-book:hover{transform:translateY(-2px);border-color:#92b6e9;box-shadow:0 14px 22px #2a437026}.kb-book-spine{background:linear-gradient(180deg,#7fb2f2,#4b8ee2)}.kb-book-main{padding:10px;display:flex;flex-direction:column;gap:8px}.kb-book-title-row{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}.kb-book-summary{margin:0;color:var(--muted);font-size:12px;line-height:1.45}.kb-book-meta{display:flex;flex-wrap:wrap;gap:8px;color:#687d9c;font-size:11px}.kb-book-actions a{display:inline-block;font-size:12px;color:#1a66c5;text-decoration:none;border:1px solid #b9d0f0;border-radius:999px;padding:4px 10px}.kb-book-actions a:hover{border-color:#7ca8e2;background:#e8f3ffe6}.kb-grade-chip{font-weight:700}.grade-s{border-color:#9dd2b5;color:#137448}.grade-a{border-color:#9dc5f4;color:#1e60b3}.grade-b{border-color:#b8c8e4;color:#365f96}.grade-c{border-color:#e0cfac;color:#8a640d}.grade-d{border-color:#e5b9b6;color:#9b3d39}.kb-shelf.grade-s .kb-book-spine{background:linear-gradient(180deg,#62c894,#2f9d69)}.kb-shelf.grade-a .kb-book-spine{background:linear-gradient(180deg,#7eb4f1,#3d7fe0)}.kb-shelf.grade-b .kb-book-spine{background:linear-gradient(180deg,#9aaed2,#7389b1)}.kb-shelf.grade-c .kb-book-spine{background:linear-gradient(180deg,#f1cb7e,#ca9a37)}.kb-shelf.grade-d .kb-book-spine{background:linear-gradient(180deg,#eca0a0,#cf6868)}.recent-case-card{text-align:left;border-radius:var(--radius-md);border:1px solid var(--line);background:#ffffffed;padding:12px;box-shadow:var(--shadow-soft);transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease;animation:fadeUp .42s ease both}.recent-case-card:hover{border-color:#95b0db;transform:translateY(-2px);box-shadow:0 14px 26px #2b487624}.recent-case-card:nth-child(1){animation-delay:40ms}.recent-case-card:nth-child(2){animation-delay:80ms}.recent-case-card:nth-child(3){animation-delay:.12s}.recent-case-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.recent-case-meta{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;color:var(--muted);font-size:12px}.glass{border:1px solid rgba(255,255,255,.8);border-radius:var(--radius-lg);background:var(--panel);-webkit-backdrop-filter:blur(12px) saturate(1.08);backdrop-filter:blur(12px) saturate(1.08);box-shadow:var(--shadow)}.topbar{padding:16px 18px;display:flex;align-items:flex-end;justify-content:space-between;gap:16px;animation:fadeUp .32s ease}.eyebrow{margin:0;color:var(--muted);font-size:12px;letter-spacing:.12em;text-transform:uppercase}.toolbar{display:flex;gap:8px;flex-wrap:wrap}input,select,button{border-radius:10px;border:1px solid var(--line);padding:10px 12px;font:inherit;transition:border-color .18s ease,box-shadow .18s ease,transform .18s ease,background-color .18s ease}input{background:#fff;min-width:120px}input:focus,select:focus,button:focus-visible{outline:none;border-color:#4a8de7;box-shadow:var(--ring)}select{background:#fff;min-width:120px}button{cursor:pointer;background:#fff}button:hover{border-color:#9bb4da}.cockpit-grid{margin-top:14px;display:grid;grid-template-columns:300px 1fr 330px;grid-template-rows:auto 350px;gap:12px;animation:fadeUp .46s ease both}.panel{padding:14px;transition:transform .2s ease,box-shadow .2s ease}.panel:hover{transform:translateY(-1px)}.left-panel,.right-panel{grid-row:1}.dag-panel{grid-column:2;grid-row:1}.bottom-panel{grid-column:1 / -1;grid-row:2}.panel-head{display:flex;align-items:center;justify-content:space-between;gap:8px}.panel-title{display:inline-flex;align-items:center;gap:8px;color:#121212;font-weight:700}.panel-title-icon{width:14px;height:14px;border-radius:4px;background:linear-gradient(145deg,#2177e8,#5bc1f1);box-shadow:0 3px 10px #3a81dc59;transform:rotate(45deg);flex:0 0 auto}.chip-wrap{display:flex;gap:6px;flex-wrap:wrap}.chip{border:1px solid var(--line);border-radius:999px;font-size:12px;color:var(--muted);padding:4px 8px}.patient-chip{display:inline-flex;align-items:center;gap:8px;padding:5px 12px;border-color:#b8d2f4;background:linear-gradient(135deg,#ecf6fff2,#dcedffe6);color:#194f9c;box-shadow:0 8px 18px #3f71c02e}.patient-chip-label{display:inline-grid;place-items:center;border-radius:999px;padding:1px 8px;font-size:11px;letter-spacing:.04em;color:#2f6ab5;background:#ffffffb3;border:1px solid rgba(130,170,226,.55)}.patient-chip strong{font-size:13px;color:#163f7c}.kv{display:flex;justify-content:space-between;gap:10px;border-bottom:1px dashed var(--line);padding:8px 0;font-size:13px}.kv span{color:var(--muted)}.dag-scroll{margin-top:10px;max-height:460px;overflow:auto}.lane{border:1px solid #d5e2f8;border-radius:12px;padding:10px;margin-bottom:10px;background:#fcfdffeb;box-shadow:inset 0 1px #ffffffa6}.lane h3{font-size:14px;margin-bottom:8px}.lane-row{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:8px}.node-card{display:flex;flex-direction:column;align-items:flex-start;gap:2px;text-align:left;border:1px solid var(--line);border-left-width:5px;border-radius:10px;background:#fff;min-height:92px;box-shadow:0 8px 18px #314c7914;transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease;position:relative;overflow:hidden;animation:fadeUp .38s ease both}.node-card:hover{transform:translateY(-2px);box-shadow:0 14px 22px #314c7924}.node-title{font-weight:700;font-size:13px}.node-key{color:var(--muted);font-size:12px}.node-meta{font-size:12px}.status-completed{color:var(--ok);border-color:#8fd6b7}.status-running{color:var(--run);border-color:#93bfff;animation:pulse 1.35s ease infinite}.status-running:after{content:"";position:absolute;top:0;right:0;bottom:0;left:0;background:linear-gradient(110deg,#fff0 28%,#91beff57,#fff0 72%);transform:translate(-115%);animation:scan 1.9s linear infinite}.status-failed,.status-error{color:var(--err);border-color:#f3b2ad}.status-paused_review_required,.status-review_required,.status-await_review,.status-warn,.status-warning{color:var(--warn);border-color:#f0d6a0}.risk-list{display:flex;flex-direction:column;gap:8px;margin-top:8px}.risk-item{border-radius:10px;padding:9px;border:1px solid var(--line);background:#fff;transition:transform .18s ease,box-shadow .18s ease}.risk-item:hover{transform:translateY(-1px);box-shadow:0 12px 18px #2941691f}.risk-item p{margin:0 0 6px;font-size:13px}.risk-item small{color:var(--muted)}.level-high{border-color:#f0b1ad}.level-medium{border-color:#ecd4a2}.timeline{margin-top:10px;max-height:290px;overflow:auto;display:flex;flex-direction:column;gap:8px}.timeline-row{display:grid;grid-template-columns:16px 1fr 170px;gap:8px;border:1px solid var(--line);border-radius:10px;padding:8px;background:#fff;transition:border-color .18s ease,box-shadow .18s ease,transform .18s ease}.timeline-row:hover{border-color:#9bb4da;transform:translateY(-1px);box-shadow:0 12px 20px #2a406b1f}.dot{width:8px;height:8px;border-radius:50%;margin-top:8px;background:#9eb2d2}.timeline-title{display:flex;justify-content:space-between;gap:8px;font-size:13px}.timeline-main p{margin:6px 0 0;color:var(--muted);font-size:13px}.timeline-side{display:flex;flex-direction:column;align-items:flex-end;gap:4px;color:var(--muted)}.muted{color:var(--muted)}.error-box{margin-top:10px;border:1px solid #f1b4b0;background:#fff2f1;border-radius:10px;padding:10px;color:#8b2e2e}.upload-card{margin-top:16px;border:1px solid var(--line);border-radius:var(--radius-md);background:#fffffff2;padding:14px;box-shadow:var(--shadow-soft);animation:fadeUp .42s ease both}.upload-stage-3{border-color:#b4d1ff;box-shadow:0 14px 28px #266ed629}.upload-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:2px 0 12px}.upload-step{border:1px solid #d3deee;border-radius:12px;padding:8px;background:#f7fbffbf;color:#7a8ca8;font-size:12px;display:flex;align-items:center;gap:8px;transition:border-color .18s ease,background-color .18s ease,color .18s ease,transform .18s ease}.upload-step.active{border-color:#8db5ef;background:#e5f1ffe0;color:#225899;transform:translateY(-1px)}.upload-step-index{width:20px;height:20px;border-radius:999px;display:grid;place-items:center;background:#dfe9f8;color:#2f598f;font-size:11px;font-weight:700;flex:0 0 auto}.upload-step.active .upload-step-index{background:linear-gradient(130deg,#257de9,#39a4ef);color:#fff}.upload-stage-note{margin:10px 0 0;color:var(--muted);font-size:12px}.upload-card-head{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:10px}.upload-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.upload-grid label,.upload-files label{font-size:12px;color:var(--muted);display:flex;flex-direction:column;gap:6px}.upload-files label{border:1px dashed #cfdbef;border-radius:12px;padding:8px;background:#ffffffb3;transition:border-color .18s ease,background-color .18s ease}.upload-files label:hover{border-color:#8caede;background:#fffffff0}.file-picker{position:relative;overflow:hidden}.file-picker.selected{border-color:#7fabe3;background:linear-gradient(180deg,#ebf5fff2,#f5fbfff2);box-shadow:inset 0 0 0 1px #78a7e74d,0 10px 18px #376ab824}.file-picker.selected:after{content:"âœ“";position:absolute;top:8px;right:10px;width:18px;height:18px;border-radius:999px;display:grid;place-items:center;background:#2f88f2;color:#fff;font-size:12px;font-weight:700}.file-picker-head{display:flex;align-items:center;justify-content:space-between;gap:8px}.file-picker-state{font-size:11px;color:#7c8ea9;border:1px solid #d3deed;border-radius:999px;padding:2px 7px}.file-picker.selected .file-picker-state{color:#1f65bc;border-color:#96bee9;background:#ecf6ffd9}.file-picker-name{font-size:11px;color:#75849c;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.file-picker.selected .file-picker-name{color:#325d94}.upload-grid .span-2{grid-column:span 2}.upload-files{margin-top:12px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.modal-wrap{position:fixed;top:0;right:0;bottom:0;left:0;background:#10172b59;display:grid;place-items:center;padding:20px}.modal-card{width:min(980px,100%);max-height:calc(100vh - 40px);overflow:auto;border-radius:14px;background:#fff;border:1px solid #dbe6f6;box-shadow:var(--shadow);padding:14px;animation:zoomIn .22s ease}.modal-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}.modal-kv{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.io-grid{margin-top:10px;display:grid;grid-template-columns:1fr 1fr;gap:10px}pre{margin:0;border-radius:10px;border:1px solid var(--line);background:#f8fbff;paddi…™Ê    ï\‰ï\‰ï\Æ           À 
Âé  ¾l          ¾l     Á c o c k p i t . j s           …/    ï\ï\ï\            À 	|€  á
           á
      Á c o m m o n . j s             …ÑØ    ï\ï\ï\           À oª  v           v      Á c o n t r a s t _ c o n t r o Á l . j s                       …öç    ï\ï\ï\           À §m  Ù>            Ù>      Á i m a g e _ c o n t r o l s . Á j s                           …!    ï\ï\ï\           À 
ïŠ  )          ! )      Á p a t i e n t . j s           …y    ï\ï\ï\           À Á  $p         # $p     Á p r o c e s s i n g . j s     …{G    ï\ï\ï\           À 	H  °          & °      Á r e p o r t . j s             …Ö‹    ï\ï\ï\           À ­4  T          ' T      Á s t r o k e _ a n a l y s i s Á _ f r o n t e n d . j s       …üí    ï\„ï\„ï\           À NN  ³s          ( ³s      Á s t r o k e c l a w _ t a s k Á s . j s                       …Zf    ï\ƒï\ƒï\           À   4          ) 4      Á s t r o k e c l a w _ w 0 . j Á s                             …­a    ï\ï\ï\           À 	¿e  6          , 6      Á u p l o a d . j s             …Ôs    ï\ï\ï\           À ùØ  ¬#          - ¬#      Á u s e r _ p r o m p t s . j s …İ¸    ï\ï\ï\           À %-  ¨‰          / ¨‰      Á v a l i d a t i o n . j s     …·>    ï\ï\ï\#           À 	z  !e         3 !e     Á v i e w e r . j s                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             let cockpitRunId = ''; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-04-23
let cockpitFileId = '';
let cockpitPatientId = '';

let cockpitRun = null;
let cockpitEvents = [];
let cockpitResult = null;
let cockpitValidation = null;
let cockpitUploadResult = null;

let cockpitPollTimer = null; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-01
let cockpitSourceTag = 'real';
let cockpitApiUrls = {
    runUrl: '',
    eventsUrl: '',
    resultUrl: '',
};

let cockpitNodes = [];
let cockpitEdges = [];
let cockpitGraphModel = null;
let cockpitSelectedNodeKey = '';
let cockpitActiveEventSeq = null;
let cockpitDagZoom = 1;
let demoAutoCollapsedOnce = false; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-02
let currentDrawerTab = 'clinical';

const COCKPIT_TERMINAL = new Set(['succeeded', 'failed', 'cancelled', 'paused_review_required']);

const STATUS_TEXT_MAP = {
    queued: 'æ’é˜Ÿä¸­',
    running: 'è¿è¡Œä¸­',
    succeeded: 'å·²å®Œæˆ',
    failed: 'å¤±è´¥',
    cancelled: 'å·²å–æ¶ˆ',
    paused_review_required: 'å¾…äººå·¥å¤æ ¸',
    pending: 'å¾…æ‰§è¡Œ',
    completed: 'å·²å®Œæˆ',
    skipped: 'å·²è·³è¿‡',
    pass: 'é€šè¿‡',
    warn: 'è­¦å‘Š',
    fail: 'å¤±è´¥',
    unavailable: 'ä¸å¯ç”¨',
    review_required: 'å¾…å¤æ ¸',
};

const STAGE_TEXT_MAP = {
    triage: 'ç—…ä¾‹è¾“å…¥',
    tooling: 'å½±åƒä¸åˆ†æ',
    icv: 'å†…åœ¨ä¸€è‡´æ€§æ ¡éªŒ',
    ekv: 'å¤–éƒ¨è¯æ®æ ¡éªŒ',
    consensus: 'ä¸€è‡´æ€§è£å†³',
    summary: 'æŠ¥å‘Šä¸æ€»ç»“',
    done: 'å®Œæˆ',
};

const CONSENSUS_TEXT_MAP = {
    accept: 'æ¥å—',
    review_required: 'éœ€å¤æ ¸',
    escalate: 'éœ€å‡çº§å¤„ç†',
    unavailable: 'ä¸å¯ç”¨',
    skipped: 'å·²è·³è¿‡',
};

const ANSWER_STATUS_TEXT_MAP = {
    pending: 'å¾…ç”Ÿæˆ',
    running: 'ç”Ÿæˆä¸­',
    ready: 'å·²ç”Ÿæˆ',
    failed: 'å¤±è´¥',
    unavailable: 'ä¸å¯ç”¨',
};

const SOURCE_CHAIN_TEXT_MAP = {
    none: 'æ— ',
    case_latest_result_json: 'ç—…ä¾‹æœ€æ–°ç»“æœ',
    run_result: 'è¿è¡Œç»“æœ',
    run_result_by_id: 'æŒ‰ run_id å‘½ä¸­è¿è¡Œç»“æœ',
    agent_run_result: 'Agent è¿è¡Œç»“æœ',
    report_payload: 'æŠ¥å‘Šè½½è·',
    local_storage_fallback: 'æœ¬åœ°å›é€€',
};

const DAG_LANES = [
    { lane_key: 'L1', title: 'ç—…ä¾‹è¾“å…¥', order: 1 },
    { lane_key: 'L2', title: 'å½±åƒåˆç­›', order: 2 },
    { lane_key: 'L3', title: 'çŒæ³¨ä¸å’ä¸­åˆ†æ', order: 3 },
    { lane_key: 'L4', title: 'å†³ç­–ä¸æŠ¥å‘Š', order: 4 },
    { lane_key: 'L5', title: 'äººå·¥å¤æ ¸ä¸å‘å¸ƒ', order: 5 },
];

const TOOL_TITLE_MAP = {
    triage_planner: 'Planner',
    detect_modalities: 'æ¨¡æ€è¯†åˆ«',
    image_qc: 'å›¾åƒè´¨æ§',
    load_patient_context: 'ç—…ä¾‹ä¸Šä¸‹æ–‡',
    run_ncct_classification: 'NCCTä¸‰åˆ†ç±»',
    run_vessel_occlusion_classification: 'è¡€ç®¡é—­å¡ä¸‰åˆ†ç±»',
    generate_ctp_maps: 'ç±»CTPç”Ÿæˆ',
    run_stroke_analysis: 'å’ä¸­è‡ªåŠ¨åˆ†æ',
    icv: 'å†…åœ¨ä¸€è‡´æ€§æ ¡éªŒ',
    ekv: 'å¤–éƒ¨è¯æ®æ ¡éªŒ',
    consensus_lite: 'ä¸€è‡´æ€§è£å†³',
    generate_structured_report: 'ç»“æ„åŒ–æŠ¥å‘Šç”Ÿæˆ',
    generate_medgemma_report: 'ç»“æ„åŒ–æŠ¥å‘Šç”Ÿæˆ',
    summary: 'æ€»ç»“',
    human_confirm: 'äººå·¥ç¡®è®¤',
    human_review: 'äººå·¥å¤æ ¸',
    export_report: 'æŠ¥å‘Šå¯¼å‡º',
    emr_sync: 'æŠ¥å‘Šå‘å¸ƒ',
    emr_sync_writeback: 'æŠ¥å‘Šå‘å¸ƒ',
    run_ai_qa: 'AI é—®è¯Š',
};

const TOOL_LANE_MAP = {
    triage_planner: 'L1',
    detect_modalities: 'L1',
    image_qc: 'L1',
    load_patient_context: 'L1',
    run_ncct_classification: 'L2',
    run_vessel_occlusion_classification: 'L3',
    generate_ctp_maps: 'L3',
    run_stroke_analysis: 'L3',
    icv: 'L4',
    ekv: 'L4',
    consensus_lite: 'L4',
    generate_structured_report: 'L4',
    generate_medgemma_report: 'L4',
    summary: 'L4',
    human_confirm: 'L5',
    human_review: 'L5',
    export_report: 'L5',
    emr_sync: 'L5',
    emr_sync_writeback: 'L5',
    run_ai_qa: 'L5',
};

const STAGE_LANE_MAP = {
    triage: 'L1',
    tooling: 'L3',
    icv: 'L4',
    ekv: 'L4',
    consensus: 'L4',
    summary: 'L4',
    done: 'L5',
};

const STEP_EVENT_ALIAS = {
    generate_ctp_maps: ['ctp_generate'],
    generate_structured_report: ['generate_medgemma_report', 'summary'],
    review_confirm: ['human_confirm', 'human_review'],
    review: ['human_review', 'human_confirm'],
};

const STEP_KEY_CANONICAL_MAP = Object.freeze({
    ctp_generate: 'generate_ctp_maps',
    vessel_occlusion: 'run_vessel_occlusion_classification',
    vessel_occlusion_classification: 'run_vessel_occlusion_classification',
});

const CTP_STEP_KEY = 'generate_ctp_maps';
const NCCT_STEP_KEY = 'run_ncct_classification';
const CONTEXT_STEP_KEY = 'load_patient_context';
const VESSEL_OCCLUSION_STEP_KEY = 'run_vessel_occlusion_classification'; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-03
const STROKE_ANALYSIS_STEP_KEY = 'run_stroke_analysis';
const CTP_SKIP_MESSAGE = 'å·²æä¾›CTPæˆ–æœ¬æ¬¡æ— éœ€ç”Ÿæˆï¼Œè·³è¿‡ç±»CTPç”Ÿæˆ';
const VESSEL_OCCLUSION_DEFAULT = 'ç­‰å¾…æ¨¡å‹é¢„æµ‹';
const VESSEL_OCCLUSION_DEFAULT_MESSAGE = 'ç»“æœï¼šç­‰å¾… DINOv3 æ¨¡å‹é¢„æµ‹...';

function setText(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = value ?? '-';
}

function mapTokenText(value, map) {
    const raw = String(value || '').trim();
    if (!raw) return '-'; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-04
    const key = raw.toLowerCase();
    return map[key] || raw;
}

function statusText(value) {
    return mapTokenText(value, STATUS_TEXT_MAP);
}

function stageText(value) {
    return mapTokenText(value, STAGE_TEXT_MAP);
}

function consensusText(value) {
    return mapTokenText(value, CONSENSUS_TEXT_MAP);
}

function sourceChainText(value) {
    return mapTokenText(value, SOURCE_CHAIN_TEXT_MAP);
}

function answerStatusText(value) {
    return mapTokenText(value, ANSWER_STATUS_TEXT_MAP);
}

function statusClass(value) {
    const token = String(value || '').toLowerCase().replace(/\s+/g, '_'); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-05
    return token ? `status-${token}` : '';
}

function normalizeStatus(value) {
    const token = String(value || '').trim().toLowerCase();
    if (!token) return 'pending';
    if (token === 'success') return 'completed';
    if (token === 'done') return 'completed';
    return token;
}

function sourceTagClass(value) {
    const token = String(value || '').trim().toLowerCase();
    if (token === 'mock' || token === 'hybrid' || token === 'real') return token;
    return 'real'; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-06
}

function sourceTagText(value) {
    return sourceTagClass(value).toUpperCase();
}

function formatTime(value) {
    if (!value) return '-';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString();
}

function formatLatency(ms) {
    const n = Number(ms);
    if (!Number.isFinite(n) || n < 0) return '-';
    return `${Math.round(n)}ms`;
}

function formatPercentFromFraction(value) {
    const n = Number(value); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-07
    if (!Number.isFinite(n)) return '-';
    return `${(n * 100).toFixed(1)}%`;
}

function formatConfidence(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return '-';
    if (n > 1) return `${Math.max(0, Math.min(100, n)).toFixed(1)}%`;
    return `${(Math.max(0, Math.min(1, n)) * 100).toFixed(1)}%`;
}

function safeJson(value) {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'string') return value;
    try {
        return JSON.stringify(value, null, 2);
    } catch (_err) {
        return String(value);
    }
}

function escapeHtml(raw) {
    return String(raw ?? '') // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-08
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function normalizeStepKey(raw) {
    const key = String(raw || '').trim();
    if (!key) return '';
    return STEP_KEY_CANONICAL_MAP[key] || key; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-09
}

function getQueryParamsWithContext(extra = {}) {
    const params = new URLSearchParams();
    const runId = extra.run_id || cockpitRunId;
    const fileId = extra.file_id || cockpitFileId;
    const patientId = extra.patient_id || cockpitPatientId;
    if (runId) params.set('run_id', runId);
    if (fileId) params.set('file_id', fileId);
    if (patientId) params.set('patient_id', String(patientId));
    Object.entries(extra).forEach(([k, v]) => {
        if (!v || ['run_id', 'file_id', 'patient_id'].includes(k)) return; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-10
        params.set(k, String(v));
    });
    return params;
}

function getViewerUrl() {
    if (!cockpitFileId) return '/viewer';
    return `/viewer?${getQueryParamsWithContext().toString()}`;
}

function getReportUrl() {
    if (!cockpitPatientId) return '/';
    return `/report/${encodeURIComponent(cockpitPatientId)}?${getQueryParamsWithContext().toString()}`;
}

function getValidationUrl(tab = 'ekv') {
    return `/validation?${getQueryParamsWithContext({ tab }).toString()}`;
}

function goBackViewer() {
    window.location.href = getViewerUrl();
}

function goBackReport() {
    if (!cockpitPatientId) {
        window.location.href = '/';
        return; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-11
    }
    window.location.href = getReportUrl();
}

function goBackValidation() {
    window.location.href = getValidationUrl('ekv');
}

function updateRunQueryString() {
    const params = getQueryParamsWithContext();
    const query = params.toString();
    const nextUrl = `${window.location.pathname}${query ? `?${query}` : ''}`;
    window.history.replaceState({}, '', nextUrl);
}

function parseCockpitParams() {
    const params = new URLSearchParams(window.location.search);
    cockpitRunId = (params.get('run_id') || cockpitRunId || '').trim();
    cockpitFileId = (params.get('file_id') || cockpitFileId || sessionStorage.getItem('current_file_id') || '').trim(); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-12
    cockpitPatientId = (params.get('patient_id') || cockpitPatientId || (typeof getCurrentPatientId === 'function' ? getCurrentPatientId() : '') || '').trim();

    if (!cockpitRunId && cockpitFileId) {
        cockpitRunId = (localStorage.getItem(`latest_agent_run_${cockpitFileId}`) || '').trim();
    }

    if (typeof setCurrentPatientId === 'function' && cockpitPatientId) {
        setCurrentPatientId(cockpitPatientId);
    }
    if (typeof setPatientInfoVisible === 'function') {
        setPatientInfoVisible(Boolean(cockpitPatientId));
    }
    if (typeof updatePatientHeader === 'function' && cockpitPatientId) {
        updatePatientHeader(cockpitPatientId);
    }

    if (cockpitRunId && !cockpitApiUrls.runUrl) {
        setApiUrlsForRun(cockpitRunId);
    }
}

function persistRunContext() {
    if (cockpitFileId && cockpitRunId) {
        localStorage.setItem(`latest_agent_run_${cockpitFileId}`, cockpitRunId);
    }
}

function updateMeta(run = {}, events = []) {
    setText('metaRunId', run.run_id || cockpitRunId || '-');
    setText('metaPatientId', run.patient_id || cockpitPatientId || '-');
    setText('metaFileId', run.file_id || cockpitFileId || '-'); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-13
    setText('metaRunStatus', statusText(run.status || '-'));
    setText('metaRunStage', stageText(run.stage || '-'));
    setText('metaCurrentTool', run.current_tool || '-');
    setText('metaEventCount', String(events.length || 0));
    setText('metaUpdatedAt', formatTime(run.updated_at || run.created_at));
}

function computeLastError(run) {
    if (!run || typeof run !== 'object') return '-';
    if (run.error) {
        if (typeof run.error === 'string') return run.error;
        return run.error.error_message || run.error.error_code || safeJson(run.error); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-14
    }
    const failedStep = [...(run.steps || [])].reverse().find((s) => normalizeStatus(s?.status) === 'failed');
    if (failedStep && failedStep.message) return failedStep.message;
    const status = normalizeStatus(run.status || '');
    if (['queued', 'running', 'succeeded', 'cancelled', 'completed'].includes(status)) return 'æ— ';
    return '-';
}

function computeRetryableStep(run) {
    if (!run || !Array.isArray(run.steps)) return '-';
    const step = [...run.steps].reverse().find((s) => normalizeStatus(s?.status) === 'failed' && s.retryable === true);
    if (!step) return 'æ— '; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-15
    const title = step.title || step.key || '-';
    const attempts = Number(step.attempts || 0);
    return `${title} (${step.key || '-'}, attempt=${attempts})`;
}

function getPlanFrames(run) {
    if (!run || !Array.isArray(run.plan_frames)) return [];
    return [...run.plan_frames]
        .filter((x) => x && typeof x === 'object')
        .sort((a, b) => Number(a.revision || 0) - Number(b.revision || 0));
}

function getCurrentPlanFrame(run) {
    const frames = getPlanFrames(run);
    if (frames.length === 0) return null; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-16
    return frames[frames.length - 1];
}

function getReplanCount(run) {
    const frames = getPlanFrames(run);
    if (frames.length === 0) return 0;
    return Math.max(0, frames.length - 1);
}

function getTerminationReason(run) {
    if (!run || typeof run !== 'object') return '-';
    if (run.termination_reason) return String(run.termination_reason);
    if (run.result && typeof run.result === 'object') {
        const r = run.result;
        if (r.termination_reason) return String(r.termination_reason); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-17
        const hint = r.context_snapshot?.working_memory?.termination_reason;
        if (hint) return String(hint);
    }
    const status = normalizeStatus(run.status || '');
    if (status === 'succeeded' || status === 'completed') return 'normal_completion';
    if (status === 'paused_review_required') return 'human_review_required';
    if (status === 'failed') return computeLastError(run);
    if (status === 'running') return 'running';
    return '-'; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-18
}

function toSummaryCount(status, count, listLike) {
    const statusToken = normalizeStatus(status || '');
    if (statusToken !== 'unavailable') {
        return String(Number.isFinite(Number(count)) ? Number(count) : 0);
    }
    if (Array.isArray(listLike) && listLike.length > 0) {
        return String(Number.isFinite(Number(count)) ? Number(count) : listLike.length);
    }
    return '-';
}

function buildThreeClassCountsText(counts) {
    if (!counts || typeof counts !== 'object') return '';
    const normalCount = Number(counts.normal || 0);
    const hemoCount = Number(counts.hemo || 0);
    const infarctCount = Number(counts.infarct || 0); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-19
    if (!Number.isFinite(normalCount) && !Number.isFinite(hemoCount) && !Number.isFinite(infarctCount)) {
        return '';
    }
    return `æ­£å¸¸ ${Number.isFinite(normalCount) ? normalCount : 0}ï¼Œè„‘å‡ºè¡€ ${Number.isFinite(hemoCount) ? hemoCount : 0}ï¼Œè„‘ç¼ºè¡€ ${Number.isFinite(infarctCount) ? infarctCount : 0}`;
}

function getThreeClassCandidates(run, resultResp) {
    const candidates = [];
    const push = (item) => {
        if (item && typeof item === 'object') candidates.push(item);
    };

    push(cockpitUploadResult);
    push(resultResp?.data?.result);
    push(run?.result);

    const payload = parseResultPayload(resultResp);
    if (payload && typeof payload === 'object') {
        push(payload); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-20
        push(payload.analysis_data);
        push(payload.analysis);
        push(payload.upload_result);
    }

    return candidates;
}

async function fetchLinkedUploadResult(run) {
    const linkedJobId = String(run?.linked_upload_job_id || '').trim();
    if (!linkedJobId) return null;
    try {
        const resp = await fetch(`/api/upload/progress/${encodeURIComponent(linkedJobId)}`);
   ï»¿"use strict"; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-25

const UPLOAD_NODES = [
    { key: "archive_ready", title: "Case_Intake.parse()", subtitle: "ç—…ä¾‹æ¥æ”¶ä¸å½’æ¡£å‡†å¤‡", chip: "Case_Intake", delegated: "" },
    { key: "modality_detect", title: "Modality_Detect.route()", subtitle: "æ¨¡æ€è¯†åˆ«ä¸è·¯å¾„åˆ¤å®š", chip: "Modality", delegated: "" },
    { key: "image_qc", title: "Image_QC.validate()", subtitle: "å›¾åƒè´¨æ§ï¼ˆè¿åŠ¨ä¼ªå½±/å¢å¼ºæ—¶ç›¸/å±‚åš/ç¼ºå¤±ï¼‰", chip: "Image_QC", delegated: "image_qc" },
    { key: "three_class", title: "Three_Class.triage()", subtitle: "NCCTä¸‰åˆ†ç±»ä¸Grad-CAM", chip: "Three_Class", delegated: "" },
    { key: "ctp_generate", title: "CTP_Generate.run()", subtitle: "çŒæ³¨å›¾è°±ç”Ÿæˆ", chip: "CTP_Gen", delegated: "generate_ctp_maps" },
    { key: "vessel_occlusion", title: "Vessel_Occlusion.classify()", subtitle: "è¡€ç®¡é—­å¡ä¸‰åˆ†ç±»", chip: "Vessel_Occlusion", delegated: "vessel_occlusion" },
    { key: "stroke_analysis", title: "Stroke_Analysis.segment()", subtitle: "å’ä¸­ç—…ç¶åˆ†æ", chip: "Analysis", delegated: "run_stroke_analysis" },
    { key: "pseudocolor", title: "Pseudocolor_Render.compose()", subtitle: "ä¼ªå½©å¯è§†åŒ–ç”Ÿæˆ", chip: "Pseudocolor", delegated: "generate_pseudocolor" },
    { key: "ai_report", title: "Report_Generate.compose()", subtitle: "ç»“æ„åŒ–æŠ¥å‘Šè‰æ‹Ÿ", chip: "Report", delegated: "generate_medgemma_report" },
];

const VESSEL_OCCLUSION_INPUT = Object.freeze({
    run_id: "",
    tool_name: "vessel_occlusion",
    classes: "æ­£å¸¸ / ä¸­è¡€ç®¡é—­å¡ / å¤§è¡€ç®¡é—­å¡",
});
const VESSEL_CLASS_KEYS = Object.freeze(["Class_0", "Class_1_LVO", "Class_2_MEVO"]);

const TOOL_META = Object.freeze({
    triage_planner: ["Triage_Planner.plan()", "ä»»åŠ¡ç¼–æ’ç”Ÿæˆ", "Plan"],
    detect_modalities: ["ClinicalNER.extract()", "ç»“æ„åŒ–æå–ä¸å¤æ ¸", "NER_Extract"],
    image_qc: ["Image_QC.validate()", "å›¾åƒè´¨æ§æ£€æŸ¥", "Image_QC"],
    load_patient_context: ["Patient_Context.load()", "æ‚£è€…ä¸Šä¸‹æ–‡åŠ è½½", "Context"],
    generate_ctp_maps: ["MRDPM_Generate.run()", "çŒæ³¨å›¾è°±ç”Ÿæˆ", "CTP_Gen"],
    vessel_occlusion: ["Vessel_Occlusion.classify()", "è¡€ç®¡é—­å¡ä¸‰åˆ†ç±»", "Vessel_Occlusion"],
    run_stroke_analysis: ["Stroke_Analysis.segment()", "å’ä¸­åŒºåŸŸåˆ†æ", "Analysis"],
    icv: ["Evidence_Check.icv()", "é™¢å†…æŒ‡æ ‡æ ¸éªŒ", "ICV"],
    ekv: ["Evidence_Check.ekv()", "æŒ‡å—è¯æ®æ ¸éªŒ", "EKV"],
    consensus_lite: ["Consensus_Lite.resolve()", "è¯æ®è£å†³", "Consensus"],
    generate_medgemma_report: ["Final_Report.compose()", "æŠ¥å‘Šç”Ÿæˆ", "Report"],
    human_confirm: ["Human_Confirm.await_action()", "äººå·¥ç¡®è®¤èŠ‚ç‚¹", "Human_Confirm"],
    emr_sync_writeback: ["EMR_Sync.writeback()", "å›å†™å½’æ¡£", "EMR_Sync"],
});

const TEMPLATES = Object.freeze({
    default: ["ç³»ç»Ÿæ­£åœ¨æ‰§è¡Œå½“å‰èŠ‚ç‚¹ã€‚", "å¤„ç†èŠ‚ç‚¹è¾“å…¥å¹¶æ¨è¿›æµç¨‹ã€‚", "å½¢æˆå¯è§£é‡Šçš„ä¸´åºŠé“¾è·¯ã€‚"],
    archive_ready: ["ç³»ç»Ÿå·²æ¥æ”¶ç—…ä¾‹å¹¶åˆ›å»ºä¼šè¯ã€‚", "å½’é›† patient_id ä¸ file_idã€‚", "ç¡®ä¿å…¨æµç¨‹åŒä¸€ç—…ä¾‹ä¸Šä¸‹æ–‡ã€‚"],
    modality_detect: ["ç³»ç»Ÿæ­£åœ¨è¯†åˆ«å¯ç”¨æ¨¡æ€ã€‚", "åˆ¤æ–­å¯æ‰§è¡Œåˆ†æè·¯å¾„ã€‚", "é¿å…è¾“å…¥ç¼ºå¤±å¯¼è‡´è¯¯åˆ¤ã€‚"],
    image_qc: ["ç³»ç»Ÿæ­£åœ¨æ‰§è¡Œå›¾åƒè´¨æ§æ£€æŸ¥ã€‚", "æ£€æµ‹è¿åŠ¨ä¼ªå½±ã€å¢å¼ºæ—¶ç›¸ã€å±‚åšå¼‚å¸¸ä¸å›¾åƒç¼ºå¤±ã€‚", "è¯„ä¼°å›¾åƒè´¨é‡é£é™©å¹¶å†³å®šæ˜¯å¦ç»§ç»­å¤„ç†ã€‚"],
    three_class: ["ç³»ç»Ÿæ­£åœ¨æ‰§è¡Œ NCCT ä¸‰åˆ†ç±»ã€‚", "åŒæ­¥ç”Ÿæˆ Grad-CAM è§£é‡Šå›¾ã€‚", "ä¸ºåç»­ä¸´åºŠåˆ¤è¯»æä¾›å¿«é€Ÿåˆ†è¯Šå‚è€ƒã€‚"],
    ctp_generate: ["ç³»ç»Ÿå°†åœ¨ä¸‰åˆ†ç±»å®Œæˆåå¯åŠ¨ CTP ç”Ÿæˆã€‚", "è¾“å‡º CBF/CBV/Tmax çŒæ³¨æ ¸å¿ƒå‚æ•°ã€‚", "æ”¯æ’‘ç¼ºè¡€æ ¸å¿ƒä¸åŠæš—å¸¦åˆ¤æ–­ã€‚"],
    vessel_occlusion: ["ç³»ç»Ÿæ­£åœ¨æ‰§è¡Œè¡€ç®¡é—­å¡ä¸‰åˆ†ç±»ã€‚", "æ‰§è¡Œè¡€ç®¡é—­å¡ä¸‰åˆ†ç±»è¯„ä¼°ã€‚", "è¾…åŠ©åˆ¤æ–­å–æ “ç›¸å…³é£é™©ä¸è´£ä»»è¡€ç®¡åˆ†å‹ã€‚"],
    stroke_analysis: ["ç³»ç»Ÿæ­£åœ¨åšç—…ç¶åˆ†å‰²ä¸ä½“ç§¯è¯„ä¼°ã€‚", "è®¡ç®—ç—…ç¶ä¾§åˆ«ä¸å…³é”®æŒ‡æ ‡ã€‚", "å½¢æˆæ²»ç–—å†³ç­–ä¾æ®ã€‚"],
    ai_report: ["ç³»ç»Ÿæ­£åœ¨ç»„è£…ç»“æ„åŒ–æŠ¥å‘Šã€‚", "æ±‡æ€»æ¨ç†è¯æ®ä¸å…³é”®ç»“è®ºã€‚", "å‡å°‘åŒ»ç”Ÿé‡å¤å½•å…¥è´Ÿæ‹…ã€‚"],
    icv: ["ç³»ç»Ÿæ­£åœ¨æ‰§è¡Œ ICV æ ¸éªŒã€‚", "æ£€æŸ¥å…³é”®æŒ‡æ ‡ä¸€è‡´æ€§ã€‚", "é™ä½æŒ‡æ ‡å†²çªé£é™©ã€‚"],
    ekv: ["ç³»ç»Ÿæ­£åœ¨æ‰§è¡Œ EKV æ ¸éªŒã€‚", "å¯¹ç…§å¾ªè¯ä¸æŒ‡å—è§„åˆ™ã€‚", "æå‡ç»“è®ºå¯ä¿¡åº¦ã€‚"],
    consensus_lite: ["ç³»ç»Ÿæ­£åœ¨åšè¯æ®å…±è¯†è£å†³ã€‚", "èåˆå¤šè·¯ç»“è®ºå¹¶å»å†²çªã€‚", "è¾“å‡ºå¯è½åœ°çš„ä¸€è‡´å»ºè®®ã€‚"],
    emr_sync_writeback: ["ç³»ç»Ÿæ­£åœ¨å›å†™å½’æ¡£ã€‚", "åŒæ­¥ç»“æ„åŒ–ç»“æœåˆ°ä¸‹æ¸¸ç³»ç»Ÿã€‚", "å½¢æˆé—­ç¯ä¸å¯è¿½æº¯è®°å½•ã€‚"],
});

const TERMINAL = new Set(["succeeded", "failed", "cancelled", "paused_review_required"]);
const REVEAL_ADVANCE_STATUSES = new Set(["completed", "waiting"]); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-26
const STATUS_TEXT = { pending: "Pending", running: "Running", completed: "Completed", issue: "Issue Found", waiting: "Await Human", needs_edit: "Needs Edit", confirmed: "Confirmed" };
const RUN_RESULT_FETCH_MAX_WAIT_MS = 30000;
const DEFAULT_NODE_VISIBLE_MS = 1000;
const NODE_PRESENTATION_MS = Object.freeze({
    three_class: 3000,
    ctp_generate: 60000,
    vessel_occlusion: 3000,
});
const PRESENTATION_PACED_NODE_KEYS = new Set(Object.keys(NODE_PRESENTATION_MS));
const NON_BLOCKING_ISSUE_KEYS = new Set(["vessel_occlusion", "icv", "ekv", "consensus_lite"]);
const REVIEW_FALLBACK_SECTIONS = [
    { section_id: "patient_context", title: "æ‚£è€…åŸºæœ¬ä¿¡æ¯ä¸æ—¶çª—", lead: "ç¡®è®¤äººå£å­¦ä¸æ—¶é—´çª—ä¿¡æ¯æ˜¯å¦å¯æ”¯æŒåç»­å†³ç­–ã€‚", guide: "è¯·æ ¸å¯¹å¹´é¾„ã€æ€§åˆ«ã€èµ·ç—…è‡³å…¥é™¢æ—¶é—´åŠ NIHSSã€‚", risk_level: "low" },
    { section_id: "imaging_summary", title: "å½±åƒæ‘˜è¦ï¼ˆNCCT/CTAï¼‰", lead: "ç¡®è®¤å½±åƒæ ¸å¿ƒå‘ç°æ˜¯å¦å‡†ç¡®å¯è¯»ã€‚", guide: "è¯·ç¡®è®¤ NCCT ä¸ CTA çš„å…³é”®å‘ç°æ˜¯å¦å®Œæ•´ã€‚", risk_level: "medium" },
    { section_id: "ctp_quant", title: "CTP é‡åŒ–åˆ†æ", lead: "ç¡®è®¤æ ¸å¿ƒæ¢—æ­»ã€åŠæš—å¸¦ä¸ä¸åŒ¹é…æ¯”å€¼ã€‚", guide: "è¯·æ ¸å¯¹ä½“ç§¯æ•°å€¼åŠä¸´åºŠæ„ä¹‰è§£é‡Šã€‚", risk_level: "medium" },
    { section_id: "question_answer", title: "é—®é¢˜é©±åŠ¨ç»“è®º", lead: "ç¡®è®¤é—®é¢˜å›ç­”ä¸ä¸´åºŠå»ºè®®æ˜¯å¦ä¸€è‡´ã€‚", guide: "è¯·æ£€æŸ¥é—®é¢˜å›ç­”ã€ç½®ä¿¡åº¦ä¸å…³é”®è¦ç‚¹ã€‚", risk_level: "medium" },
    { section_id: "risk_uncertainty", title: "é£é™©ä¸ä¸ç¡®å®šé¡¹", lead: "é«˜é£é™©ä¸ä¸ç¡®å®šé¡¹éœ€è¦æ˜¾å¼ç¡®è®¤ã€‚", guide: "è¯·ç¡®è®¤é£é™©æç¤ºå’Œå»ºè®®å¤æ ¸é¡¹ã€‚", risk_level: "high" },
    { section_id: "next_steps", title: "ä¸‹ä¸€æ­¥å»ºè®®", lead: "ç¡®è®¤ä¸‹ä¸€æ­¥æ£€æŸ¥æˆ–æ²»ç–—åŠ¨ä½œã€‚", guide: "è¯·ç¡®è®¤å»ºè®®æ˜¯å¦å¯æ‰§è¡Œä¸”é¡ºåºåˆç†ã€‚", risk_level: "medium" },
    { section_id: "evidence_trace", title: "è¯æ®è¿½æº¯", lead: "æ ¸å¯¹ç»“è®ºä¸è¯æ®æ˜ å°„å…³ç³»ã€‚", guide: "è¯·ç¡®è®¤å…³é”®ç»“è®ºå‡æœ‰è¯æ®æ”¯æ’‘ã€‚", risk_level: "low" },
];

const state = {
    jobId: "", patientId: "", fileId: "", runId: "", startedAt: "",
    uploadTimer: null, runTimer: null, uploadDone: false, runResultFetched: false,
    latestJob: null, latestRun: null, events: [], hints: {}, nodes: [],
    error: "", redirecting: false, awaitingReport: false,
    runTerminalAt: 0, reportResultRetryUntil: 0, lastManualScrollAt: 0, lastFocusNode: "",
    expanded: Object.create(null),
    revealedNodeIds: [],
    revealPendingIds: [],
    revealTimer: null,
    revealTimerDue: 0,
    revealAt: Object.create(null),
    renderedFeedIds: Object.create(null),
    viewerDelayTimer: null,
    review: {
        required: false,
        visible: false,
        loading: false,
        saving: false,
        offlineMode: false,
        error: "",
        info: "",
        state: null,
        currentSectionId: "",
        rewriteSuggestion: null,
        pendingOps: [],
        flushInFlight: false,
        inited: false,
    },
};

const $ = (id) => document.getElementById(id);
const t = (v, d = "-") => (v === null || v === undefined || String(v).trim() === "" ? d : String(v).trim()); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-27
const token = (v) => String(v || "").trim().toLowerCase();

function normStatus(v) {
    const s = token(v);
    if (!s || ["queued", "pending", "idle"].includes(s)) return "pending";
    if (["running", "processing", "in_progress"].includes(s)) return "running";
    if (["completed", "succeeded", "done", "skipped"].includes(s)) return "completed";
    if (["paused_review_required", "review_required", "await_review", "waiting"].includes(s)) return "waiting";
    if (["issue", "failed", "cancelled", "error", "warn", "warning", "unavailable"].includes(s)) return "issue";
    return "pending"; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-28
}

function objectValue(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

function normalizeVesselOcclusionResult(value) {
    const wrapped = objectValue(value);
    const source = objectValue(wrapped?.vessel_occlusion_result) || wrapped;
    if (!source || ![
        "vessel_occlusion_status", "vessel_occlusion_class_result", "predicted_label", "predicted_class",
        "class_counts", "error_code", "failures", "valid_predictions",
    ].some((key) => Object.prototype.hasOwnProperty.call(source, key))) return null;

    const label = t(source.vessel_occlusion_class_result || source.predicted_label, "");
    let status = token(source.status || source.vessel_occlusion_status);
    const rawCounts = objectValue(source.class_counts) || objectValue(source.vessel_occlusion_class_counts) || {};
    const validPredictionsValue = Number(source.valid_predictions);
    const hasPredictionEvidence = VESSEL_CLASS_KEYS.includes(source.predicted_class)
        || (Number.isFinite(validPredictionsValue) && validPredictionsValue > 0)
        || VESSEL_CLASS_KEYS.some((key) => Number(rawCounts[key]) > 0);
    if (!["completed", "failed", "unavailable"].includes(status)) {
        status = label && hasPredictionEvidence ? "completed" : "unavailable";
    }
    if (status === "completed" && (!label || !hasPredictionEvidence)) status = "failed";

    const confidenceValue = Number(source.confidence ?? source.vessel_occlusion_confidence);
    const confidence = Number.isFinite(confidenceValue) && confidenceValue >= 0 && confidenceValue <= 1 ? confidenceValue : null;
    const sourceCounts = rawCounts;
    const classCounts = {};
    VESSEL_CLASS_KEYS.forEach((key) => {
        const count = Number(sourceCounts[key]);
        classCounts[key] = Number.isFinite(count) && count >= 0 ? Math.trunc(count) : 0;
    });
    const totalSlices = Number(source.total_slices);
    const validPredictions = validPredictionsValue;

    return {
        ...source,
        status,
        vessel_occlusion_class_result: status === "completed" ? (label || null) : null,
        predicted_class: status === "completed" && VESSEL_CLASS_KEYS.includes(source.predicted_class) ? source.predicted_class : null,
        confidence: status === "completed" ? confidence : null,
        class_counts: status === "completed" ? classCounts : Object.fromEntries(VESSEL_CLASS_KEYS.map((key) => [key, 0])),
        total_slices: Number.isFinite(totalSlices) && totalSlices >= 0 ? Math.trunc(totalSlices) : 0,
        valid_predictions: status === "completed" && Number.isFinite(validPredictions) && validPredictions >= 0 ? Math.trunc(validPredictions) : 0,
        error_code: t(source.error_code, "") || null,
        error_message: t(source.error_message || source.fallback_reason, "") || null,
        failures: Array.isArray(source.failures) ? source.failures : [],
    };
}

function vesselOcclusionResult(jobStep = null, hint = null) {
    const toolResults = Array.isArray(state.latestRun?.tool_results) ? state.latestRun.tool_results : [];
    const vesselToolResult = toolResults.slice().reverse().find((item) => token(item?.tool_name) === "vessel_occlusion");
    const candidates = [
        state.latestRun?.result?.vessel_occlusion_result,
        state.latestRun?.result,
        vesselToolResult?.structured_output,
        vesselToolResult?.output,
        state.latestJob?.result?.vessel_occlusion_result,
        state.latestJob?.result,
        hint?.output,
        jobStep?.result,
        jobStep?.output,
        jobStep?.output_ref,
    ];
    for (const candidate of candidates) {
        const normalized = normalizeVesselOcclusionResult(candidate);
        if (normalized) return normalized;
    }
    return null;
}

function vesselFailureText(result, fallback = "") {
    const failure = Array.isArray(result?.failures)
        ? result.failures.map((item) => typeof item === "string" ? t(item, "") : t(item?.error_message || item?.message || item?.error, "")).find(Boolean)
        : "";
    const message = t(result?.error_message, "") || failure || t(fallback, "");
    const code = t(result?.error_code, "");
    if (code && message && !message.includes(code)) return `${message} (${code})`;
    if (code) return code;
    return message || (result?.status === "unavailable" ? "æœªè·å¾—æ¨¡å‹ç»“æœ" : "è¡€ç®¡é—­å¡ä¸‰åˆ†ç±»æ‰§è¡Œå¤±è´¥");
}

function vesselResultText(result, fallback = "") {
    if (!result) return t(fallback, "è¡€ç®¡é—­å¡ä¸‰åˆ†ç±»å·²å®Œæˆ");
    if (result.status !== "completed") return vesselFailureText(result, fallback);
    const label = t(result.vessel_occlusion_class_result || result.predicted_class, "");
    const parts = [label];
    if (Number.isFinite(result.confidence)) parts.push(`ç½®ä¿¡åº¦ ${(result.confidence * 100).toFixed(1)}%`);
    const counts = objectValue(result.class_counts) || {};
    if (VESSEL_CLASS_KEYS.some((key) => Number(counts[key]) > 0)) {
        parts.push(`LVO=${Number(counts.Class_1_LVO) || 0} MeVO=${Number(counts.Class_2_MEVO) || 0} Normal=${Number(counts.Class_0) || 0}`);
    }
    return parts.filter(Boolean).join(" | ") || t(fallback, "è¡€ç®¡é—­å¡ä¸‰åˆ†ç±»å·²å®Œæˆ");
}

function statusIcon(s) { return s === "running" ? "â—‰" : s === "completed" ? "âœ“" : s === "issue" ? "!" : s === "waiting" ? "â¸" : "â—‹"; }
function summarize(v) {
    if (v === null || v === undefined) return "-";
    if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") return String(v);
    if (Array.isArray(v)) return `[${v.slice(0, 5).map((x) => summarize(x)).join(", ")}${v.length > 5 ? ", ..." : ""}]`;
    if (typeof v === "object") {
        if (v.error_message) return String(v.error_message);
        if (v.message) return String(v.message);
        const keys = Object.keys(v);
        return keys.slice(0, 8).map((k) => `${k}: ${summarize(v[k])}`).join("\n");
    }
    return String(v);
}
function pretty(v) { try { return typeof v === "object" ? JSON.stringify(v, null, 2) : String(v); } catch (_e) { return summarize(v); } } // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-29
function modalities() { return Array.isArray(state.latestJob?.modalities) && state.latestJob.modalities.length ? state.latestJob.modalities : (Array.isArray(state.latestRun?.planner_input?.available_modalities) ? state.latestRun.planner_input.available_modalities : []); }
function threeClassSummaryText() {
    const summary = state.latestJob?.result?.three_class_summary;
    if (!summary) return "-";
    if (typeof summary === "string") return summary;
    if (typeof summary.display === "string" && summary.display.trim()) return summary.display.trim();
    const counts = summary.counts && typeof summary.counts === "object" ? summary.counts : {};
    const parts = [];
    const map = [
        ["normal", "æ­£å¸¸"],
        ["hemo", "è„‘å‡ºè¡€"],
        ["infarct", "è„‘ç¼ºè¡€"],
    ]; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-30
    map.forEach(([key, label]) => {
        if (counts[key] !== undefined && counts[key] !== null) {
            parts.push(`${label} ${counts[key]}`);
        }
    });
    return parts.length ? parts.join(" | ") : "-";
}

function threeClassConfidenceValue() {
    const result = state.latestJob?.result || {};
    const direct = Number(result.three_class_confidence);
    if (Number.isFinite(direct)) return direct;

    const rgbFiles = Array.isArray(result.rgb_files) ? result.const STROKECLAW_TERMINAL_STATUSES = new Set([
    "succeeded",
    "failed",
    "cancelled",
    "paused_review_required",
]); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-24

const STROKECLAW_STATUS_TEXT = {
    idle: "å¾…æœº",
    ready: "å°±ç»ª",
    queued: "æ’é˜Ÿä¸­",
    running: "è¿è¡Œä¸­",
    succeeded: "å·²å®Œæˆ",
    completed: "å®Œæˆ",
    failed: "å¤±è´¥",
    cancelled: "å·²å–æ¶ˆ",
    paused_review_required: "å¾…äººå·¥å¤æ ¸",
    input_missing: "è¾“å…¥ç¼ºå¤±",
};

const STROKECLAW_EVENT_TEXT = {
    plan_created: "è®¡åˆ’å·²ç”Ÿæˆ",
    step_started: "æ­¥éª¤å¼€å§‹",
    step_completed: "æ­¥éª¤å®Œæˆ",
    issue_found: "å‘ç°é—®é¢˜",
    human_review_required: "éœ€è¦äººå·¥ç¡®è®¤",
    human_review_completed: "äººå·¥ç¡®è®¤å®Œæˆ",
    writeback_completed: "å†™å›å®Œæˆ",
};

const STROKECLAW_TOOL_TITLES = {
    detect_modalities: "Case_Intake.parse()",
    image_qc: "Image_QC.validate()",
    load_patient_context: "Patient_Context.load()",
    generate_ctp_maps: "MRDPM_Generate.run()",
    run_stroke_analysis: "Stroke_Analysis.segment()",
    icv: "Evidence_Check.icv()",
    ekv: "Evidence_Check.ekv()",
    consensus_lite: "Evidence_Check.consensus()",
    generate_medgemma_report: "Report_Generate.compose()",
};

const state = {
    tasks: [],
    selectedTaskId: "",
    preview: null,
    previewFingerprint: "",
    runId: "",
    run: null,
    events: [],
    pollTimer: null,
};

function getEl(id) {
    return document.getElementById(id);
}

function toToken(value, fallback = "") {
    const raw = String(value || "").trim().toLowerCase();
    return raw || fallback;
}

function statusText(value) {
    const token = toToken(value);
    return STROKECLAW_STATUS_TEXT[token] || value || "-";
}

function eventTypeText(value) {
    const token = toToken(value);
    return STROKECLAW_EVENT_TEXT[token] || value || "äº‹ä»¶";
}

function toolTitle(toolName) {
    const token = String(toolName || "").trim(); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-25
    return STROKECLAW_TOOL_TITLES[token] || token || "-";
}

function setHint(message, type = "") {
    const hint = getEl("scFormHint");
    if (!hint) return;
    hint.textContent = message || "";
    hint.classList.remove("error", "success");
    if (type) {
        hint.classList.add(type);
    }
}

function updateTriggerText(message) {
    const el = getEl("scTriggerText");
    if (el) {
        el.textContent = message || "æœªè§¦å‘ä»»åŠ¡ã€‚è¯·é€‰æ‹©ç—…ä¾‹åç”Ÿæˆç¼–æ’è®¡åˆ’ã€‚"; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-26
    }
}

function getCheckedModalities() {
    return Array.from(
        document.querySelectorAll(".sc-modality-wrap input[type='checkbox']:checked")
    )
        .map((item) => String(item.value || "").trim().toLowerCase())
        .filter(Boolean);
}

function setCheckedModalities(modalities) {
    const normalized = new Set((modalities || []).map((item) => String(item).trim().toLowerCase()));
    document
        .querySelectorAll(".sc-modality-wrap input[type='checkbox']")
        .forEach((item) => {
            item.checked = normalized.has(String(item.value || "").trim().toLowerCase()); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-27
        });
}

function currentFormPayload() {
    const patientId = Number(getEl("scPatientId")?.value || 0);
    const fileId = String(getEl("scFileId")?.value || "").trim();
    const goalQuestion = String(getEl("scGoalQuestion")?.value || "").trim();
    const availableModalities = getCheckedModalities();
    return {
        patient_id: patientId,
        file_id: fileId,
        goal_question: goalQuestion,
        available_modalities: availableModalities,
    };
}

function buildFingerprint(payload) {
    return JSON.stringify({
        patient_id: payload.patient_id || 0,
        file_id: payload.file_id || "",
        goal_question: payload.goal_question || "",
        available_modalities: (payload.available_modalities || []).slice().sort(),
    });
}

function setStatusPill(id, statusToken) {
    const pill = getEl(id);
    if (!pill) return; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-28
    const token = toToken(statusToken, "idle");
    pill.textContent = statusText(token);
    pill.className = `sc-status-pill ${token}`;
}

function selectedTask() {
    return state.tasks.find((item) => item.task_id === state.selectedTaskId) || null;
}

function applyTaskToForm(task) {
    if (!task) return;
    if (getEl("scPatientId")) getEl("scPatientId").value = task.patient_id || "";
    if (getEl("scFileId")) getEl("scFileId").value = task.file_id || "";
    if (getEl("scGoalQuestion")) getEl("scGoalQuestion").value = task.goal_question || "";
    setCheckedModalities(task.available_modalities || []); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-29
    updateTriggerText(
        `ä»»åŠ¡å·²é€‰ä¸­ï¼špatient ${task.patient_id} / file ${task.file_id}ã€‚å…ˆé¢„è§ˆè®¡åˆ’ï¼Œå†ç¡®è®¤æ‰§è¡Œã€‚`
    );
}

function renderTaskList() {
    const list = getEl("scTaskList");
    if (!list) return;
    list.innerHTML = "";

    if (!Array.isArray(state.tasks) || state.tasks.length === 0) {
        list.innerHTML = '<div class="sc-empty">æš‚æ— ä»»åŠ¡æ•°æ®ï¼Œè¯·å…ˆä¸Šä¼ ç—…ä¾‹å½±åƒã€‚</div>';
        return;
    }

    state.tasks.forEach((task) => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = `sc-task-item${task.task_id === state.selectedTaskId ? " active" : ""}`;
        item.dataset.taskId = task.task_id;
        item.innerHTML = `
            <div class="sc-task-head">
                <div class="sc-task-title">${task.patient_name || `Patient ${task.patient_id}`}</div>
                <span class="sc-status-pill ${toToken(task.status, "idle")}">${statusText(task.status)}</span>
            </div>
            <div class="sc-task-id">file_id: ${task.file_id || "-"}</div>
            <div class="sc-task-meta">${task.modality_summary || "-"}</div>
            <div class="sc-task-meta">path: ${task.imaging_path || "unknown"} Â· updated: ${task.updated_at || "-"}</div>
        `;
        item.addEventListener("click", () => {
            state.selectedTaskId = task.task_id; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-30
            applyTaskToForm(task);
            renderTaskList();
        });
        list.appendChild(item);
    });
}

async function fetchTasks() {
    const refreshBtn = getEl("scRefreshTasksBtn");
    if (refreshBtn) refreshBtn.disabled = true;
    try {
        const response = await fetch("/api/strokeclaw/tasks"); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-31
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.error || `ä»»åŠ¡åŠ è½½å¤±è´¥ (${response.status})`);
        }
        state.tasks = Array.isArray(data.tasks) ? data.tasks : [];
        const hasPresetFields = Boolean(
            String(getEl("scPatientId")?.value || "").trim() ||
                String(getEl("scFileId")?.value || "").trim()
        );
        if (!state.selectedTaskId && state.tasks.length > 0 && !hasPresetFields) {
            state.selectedTaskId = state.tasks[0].task_id;
            applyTaskToForm(state.tasks[0]);
        }
        renderTaskList();
    } catch (error) {
        state.tasks = [];
        renderTaskList(); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-04-01
        setHint(`ä»»åŠ¡å·¥ä½œå°åŠ è½½å¤±è´¥ï¼š${error.message}`, "error");
    } finally {
        if (refreshBtn) refreshBtn.disabled = false;
    }
}

function renderPlanMeta(preview) {
    const wrap = getEl("scPlanMeta");
    if (!wrap) return;
    wrap.innerHTML = "";
    if (!preview) return;

    const plannerOutput = preview.planner_output || {};
    const modalitySummary = (preview.modality_labels || []).join(" + ") || "-";
    const goalQuestion = preview.goal_question || "æœªè®¾ç½®"; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-04-02
    const items = [
        { label: "Path", value: plannerOutput.imaging_path || "-" },
        { label: "Modalities", value: modalitySummary },
        { label: "Goal", value: goalQuestion },
    ];

    items.forEach((item) => {
        const node = document.createElement("div");
        node.className = "sc-plan-meta-item";
        node.innerHTML = `
            <span class="label">${item.label}</span>
            <span class="value">${item.value}</span>
        `;
        wrap.appendChild(node);
    });
}

function normalizeNodeStatus(status) {
    const token = toToken(status, "pending");
    if (token === "running") return "running";
    if (token === "completed" || token === "succeeded" || token === "skipped") return "completed"; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-04-03
    if (token === "failed" || token === "issue") return "issue";
    if (token === "paused_review_required" || token === "waiting") return "waiting";
    return "pending";
}

function deriveNodeRuntimeState(previewNodes, run, events) {
    const nodeStates = {};
    (previewNodes || []).forEach((node) => {
        nodeStates[node.key] = {
            status: "pending",
            message: "",
            input_hint: node.input_hint || "",
            output_hint: node.output_hint || "",
        };
    });

    const steps = Array.isArray(run?.steps) ? run.steps : [];
    steps.forEach((step) => {
        if (!step || !step.key || !nodeStates[step.key]) return;
        nodeStates[step.key].status = normalizeNodeStatus(step.status); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-04-04
        nodeStates[step.key].message = String(step.message || "").trim();
    });

    const sortedEvents = (Array.isArray(events) ? events : [])
        .slice()
        .sort((a, b) => Number(a?.event_seq || 0) - Number(b?.event_seq || 0));

    sortedEvents.forEach((event) => {
        const toolName = String(event?.tool_name || "").trim();
        if (!toolName || !nodeStates[toolName]) return;
        const eventType = toToken(event?.event_type); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-04-05
        const eventStatus = toToken(event?.status);
        let resolvedStatus = nodeStates[toolName].status;
        if (eventType === "issue_found" || eventStatus === "failed") {
            resolvedStatus = "issue";
        } else if (
            eventType === "human_review_required" ||
            eventStatus === "paused_review_required"
        ) {
            resolvedStatus = "waiting";
        } else if (eventStatus === "running" || eventType === "step_started") {
            resolvedStatus = "running";
        } else if (eventType === "step_completed" || eventStatus === "completed") {
            resolvedStatus = "completed";
        }
        nodeStates[toolName].status = resolvedStatus; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-04-06
        if (event?.input_ref) {
            nodeStates[toolName].input_hint = JSON.stringify(event.input_ref);
        }
        if (event?.output_ref) {
            nodeStates[toolName].output_hint = JSON.stringify(event.output_ref);
        }
    });

    return nodeStates;
}

function ensurePreviewFromRun(run) {
    if (state.preview || !run) return;
    const plannerOutput = run?.planner_output || {};
    const planFrames = Array.isArray(run?.plan_frames) ? run.plan_frames : [];
    const latestPlanFrame = planFrames.length > 0 ? planFrames[planFrames.length - 1] : null; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-04-07
    const frameTools = Array.isArray(latestPlanFrame?.next_tools)
        ? latestPlanFrame.next_tools
        : [];
    const plannerTools = Array.isArray(plannerOutput?.tool_sequence)
        ? plannerOutput.tool_sequence
        : [];
    const stepTools = Array.isArray(run?.steps)
        ? run.steps.map((item) => item?.key).filter(Boolean) // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-04-08
        : [];
    const toolSequence = frameTools.length
        ? frameTools
        : plannerTools.length
        ? plannerTools
        : stepTools;
    if (!toolSequence.length) return;

    const nodes = toolSequence.map((tool, index) => ({
        index: index + 1,
        key: tool,
        title: toolTitle(tool),
        description: "",
        phase: String(run?.stage || "tooling"),
        status: "pending",
        input_hint: `run_id=${run?.run_id || "-"}`,
        output_hint: "waiting for runtime",
    })); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-04-09

    const plannerInput = run?.planner_input || {};
    const availableModalities = Array.isArray(plannerInput?.available_modalities)
        ? plannerInput.available_modalities
        : [];
    state.preview = {
        patient_id: Number(run?.patient_id || plannerInput?.patient_id || 0) || 0,
        file_id: String(run?.file_id || plannerInput?.file_id || ""),
        goal_question: String(
            plannerInput?.goal_question || plannerInput?.question || ""
        ),
        available_modalities: availableModalities,
        modality_labels: availableModalities,
        planner_output: plannerOutput,
        plan_frames: planFrames,
        replan_count: Number(run?.replan_count || 0),
        nodes,
        orchestration_brief: "å·²ä»è¿è¡Œæ€æ¢å¤è®¡åˆ’è§†å›¾ã€‚",
    };
}

function nodeHeaderStatusClass(status) {
    if (status === "running") return "node-running";
    if (status === "completed") return "node-completed";
    if (status === "issue") return "node-issue"; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-04-10
    if (status === "waiting") return "node-waiting";
    return "";
}

function renderNodeList(preview, run, events) {
    const wrap = getEl("scNodeList");
    if (!wrap) return;
    wrap.innerHTML = "";

    const nodes = Array.isArray(preview?.nodes) ? preview.nodes : [];
    if (nodes.length === 0) {
        wrap.innerHTML = '<div class="sc-empty">æš‚æ— è®¡åˆ’èŠ‚ç‚¹ã€‚</div>';
        return;
    }

    const nodeStates = deriveNodeRuntimeState(nodes, run, events); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-04-11
    nodes.forEach((node) => {
        const runtimeState = nodeStates[node.key] || {};
        const status = runtimeState.status || "pending";
        const statusToken = normalizeNodeStatus(status);
        const card = document.createElement("article");
        card.className = `sc-node-card ${nodeHeaderStatusClass(statusToken)}`.trim();
        card.innerHTML = `
            <button type="button" class="sc-node-head" data-tool="${node.key}">
                <span class="idx">${node.index}</span>
                <span class="title">${node.title || toolTitle(node.key)}</span>
                <span class="desc">${node.description || ""}</span>
                <span class="sc-status-pill ${statusToken}">${statusText(statusToken)}</span>
                <span class="toggle">å±•å¼€</span>
            </button>
            <div class="sc-node-body" hidden>
                <div class="sc-node-io">
                    <div><strong>INPUT</strong> ${runtimeState.input_hint || node.input_hint || "-"}</div>
                    <div><strong>OUTPUT</strong> ${runtimeState.output_hint || node.output_hint || "-"}</div>
                </div>
                <div class="sc-node-result ${statusToken === "issue" ? "issue" : ""}">
                    <strong>RESULT</strong> ${runtimeState.message || "ç­‰å¾…æ‰§è¡Œ..."}
                </div>
            </div>
        `;

        const head = card.querySelector(".sc-node-head");
        const body = card.querySelector(".sc-node-body");
        const toggle = card.querySelector(".toggle");
        head?.addEventListener("click", () => {
            const hidden = body?.hasAttribute("hidden"); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-04-12
            if (!body || !toggle) return;
            if (hidden) {
                body.removeAttribute("hidden");
                toggle.textContent = "æ”¶èµ·";
            } else {
                body.setAttribute("hidden", "hidden");
                toggle.textContent = "å±•å¼€";
            }
        });
        wrap.appendChild(card);
    }); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-04-13
}

function renderRunMeta(run) {
    getEl("scRunId").textContent = run?.run_id || state.runId || "-";
    getEl("scRunStage").textContentlet w0RunId = ""; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-11
let w0PatientId = "";
let w0FileId = "";
let w0PollTimer = null;
const W0_MOCK_RUN_ID_PREFIX = "w0m_";

const W0_TERMINAL_STATUSES = new Set([
    "succeeded",
    "failed",
    "cancelled",
    "paused_review_required",
]);

const STATUS_TEXT_MAP = {
    queued: "æ’é˜Ÿä¸­",
    running: "è¿è¡Œä¸­",
    succeeded: "å·²å®Œæˆ",
    failed: "å¤±è´¥",
    cancelled: "å·²å–æ¶ˆ",
    paused_review_required: "å¾…äººå·¥å¤æ ¸",
};

const EVENT_TYPE_TEXT_MAP = {
    plan_created: "è®¡åˆ’å·²ç”Ÿæˆ",
    step_started: "æ­¥éª¤å¼€å§‹",
    step_completed: "æ­¥éª¤å®Œæˆ",
    issue_found: "å‘ç°é—®é¢˜",
    human_review_required: "ç­‰å¾…äººå·¥å¤æ ¸",
    human_review_completed: "äººå·¥å¤æ ¸å®Œæˆ",
    writeback_completed: "å›å†™å®Œæˆ",
};

const TOOL_TITLE_MAP = {
    detect_modalities: "Case_Intake.parse()",
    image_qc: "Image_QC.validate()",
    load_patient_context: "Patient_Context.load()",
    generate_ctp_maps: "MRDPM_Generate.run()",
    run_stroke_analysis: "Stroke_Analysis.segment()",
    icv: "Evidence_Check.icv()",
    ekv: "Evidence_Check.ekv()",
    consensus_lite: "Evidence_Check.consensus()",
    generate_medgemma_report: "Report_Generate.compose()",
};

function setText(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = value || "-"; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-12
}

function statusText(status) {
    const token = String(status || "").trim().toLowerCase();
    return STATUS_TEXT_MAP[token] || status || "-";
}

function eventTypeText(eventType) {
    const token = String(eventType || "").trim().toLowerCase();
    return EVENT_TYPE_TEXT_MAP[token] || eventType || "æ­¥éª¤äº‹ä»¶";
}

function toolTitle(toolName) {
    const token = String(toolName || "").trim();
    if (!token) return "-";
    return TOOL_TITLE_MAP[token] || token;
}

function getCheckedModalities() {
    return Array.from(document.querySelectorAll(".w0-modality-group input[type='checkbox']:checked")) // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-13
        .map((item) => item.value)
        .filter(Boolean);
}

function updateHint(message, isError = false) {
    const hint = document.getElementById("w0Hint");
    if (!hint) return;
    hint.textContent = message;
    hint.classList.toggle("error", Boolean(isError));
}

function getPlanToolsFromRun(run) {
    if (!run || typeof run !== "object") return [];

    const planFrames = Array.isArray(run.plan_frames) ? run.plan_frames : []; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-14
    if (planFrames.length > 0) {
        const current = planFrames[planFrames.length - 1] || {};
        const nextTools = Array.isArray(current.next_tools) ? current.next_tools : [];
        if (nextTools.length > 0) return nextTools;
    }

    const plannerOutput = run.planner_output || {};
    const plannerTools = Array.isArray(plannerOutput.tool_sequence)
        ? plannerOutput.tool_sequence
        : [];
    if (plannerTools.length > 0) return plannerTools; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-15

    const steps = Array.isArray(run.steps) ? run.steps : [];
    if (steps.length > 0) return steps.map((item) => item.key).filter(Boolean);

    return [];
}

function renderPlan(run) {
    const list = document.getElementById("w0PlanList");
    if (!list) return;
    list.innerHTML = "";

    const tools = getPlanToolsFromRun(run);
    if (tools.length === 0) {
        const li = document.createElement("li"); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-16
        li.className = "empty";
        li.textContent = "è®¡åˆ’å°šæœªç”Ÿæˆï¼Œç­‰å¾… triage_planner å®Œæˆã€‚";
        list.appendChild(li);
        return;
    }

    tools.forEach((tool, index) => {
        const li = document.createElement("li");
        li.className = "plan-item";
        li.innerHTML = `<span class="idx">${index + 1}</span><span class="name">${toolTitle(tool)}</span>`;
        list.appendChild(li);
    }); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-17
}

function renderRun(run) {
    setText("w0RunId", run?.run_id || w0RunId || "-");
    setText("w0RunStatus", statusText(run?.status));
    setText("w0RunStage", run?.stage || "-");
    setText("w0CurrentTool", run?.current_tool || "-");
    setText("w0TerminationReason", run?.termination_reason || "-");
    setText("w0ReplanCount", String(run?.replan_count ?? 0));
    renderPlan(run);
}

function renderEvents(events) {
    const wrap = document.getElementById("w0EventList"); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-18
    if (!wrap) return;
    wrap.innerHTML = "";

    const rows = Array.isArray(events) ? events : [];
    if (rows.length === 0) {
        wrap.innerHTML = '<div class="empty">æš‚æ— äº‹ä»¶ã€‚</div>';
        return;
    }

    rows
        .slice()
        .sort((a, b) => Number(a?.event_seq || 0) - Number(b?.event_seq || 0))
        .forEach((event) => {
            const row = document.createElement("div"); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-19
            row.className = "event-row";
            const seq = Number(event?.event_seq || 0);
            row.innerHTML = `
                <div class="row-head">
                    <span class="seq">#${seq || "-"}</span>
                    <span class="type">${eventTypeText(event?.event_type)}</span>
                    <span class="status">${statusText(event?.status)}</span>
                </div>
                <div class="row-meta">
                    <span>${toolTitle(event?.tool_name)}</span>
                    <span>${event?.timestamp || "-"}</span>
                </div>
            `;
            wrap.appendChild(row);
        });
}

function buildCockpitUrl() {
    const params = new URLSearchParams();
    if (w0RunId && !isMockRunId(w0RunId)) params.set("run_id", w0RunId);
    if (w0FileId) params.set("file_id", w0FileId);
    if (w0PatientId) params.set("patient_id", w0PatientId); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-20
    const query = params.toString();
    return query ? `/cockpit?${query}` : "/cockpit";
}

function buildUploadUrl(patientId) {
    const params = new URLSearchParams();
    if (patientId) {
        params.set("patient_id", String(patientId));
    }
    const query = params.toString();
    return query ? `/upload?${query}` : "/upload";
}

function stopPolling() {
    if (!w0PollTimer) return;
    clearInterval(w0PollTimer);
    w0PollTimer = null;
}

function startPolling() {
    if (w0PollTimer) return; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-21
    w0PollTimer = setInterval(fetchRunAndEvents, 1500);
}

function isMockRunId(runId) {
    const token = String(runId || "").trim();
    return token.startsWith(W0_MOCK_RUN_ID_PREFIX);
}

async function fetchRunAndEvents() {
    if (!w0RunId) return;
    if (!isMockRunId(w0RunId)) {
        stopPolling();
        updateHint("å½“å‰ run ä¸æ˜¯ W0 Mock runï¼Œè”è°ƒé¡µä»…æ”¯æŒ w0m_ å‰ç¼€ runã€‚", true);
        return;
    }
    try {
        const [runResp, eventsResp] = await Promise.all([
            fetch(`/api/strokeclaw/w0/mock-runs/${encodeURIComponent(w0RunId)}`),
            fetch(`/api/strokeclaw/w0/mock-runs/${encodeURIComponent(w0RunId)}/events`),
        ]); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-22

        const runData = await runResp.json();
        const eventsData = await eventsResp.json();

        if (!runResp.ok || !runData.success) {
            throw new Error(runData.error || `è·å– run å¤±è´¥ (${runResp.status})`);
        }
        if (!eventsResp.ok || !eventsData.success) {
            throw new Error(eventsData.error || `è·å– events å¤±è´¥ (${eventsResp.status})`);
        }

        const run = runData.run || {};
        renderRun(run);
        renderEvents(eventsData.events || []);

        if (W0_TERMINAL_STATUSES.has(String(run.status || "").toLowerCase())) {
            stopPolling();
            updateHint(`Run å·²ç»“æŸï¼š${statusText(run.status)}`);
        } else {
            updateHint(`Run è¿›è¡Œä¸­ï¼š${statusText(run.status)} / ${run.stage || "-"}`);
        }
    } catch (err) {
        stopPolling();
        updateHint(`è½®è¯¢å¤±è´¥ï¼š${err.message}`, true);
    }
}

async function startW0Run() {
    const patientInput = document.getElementById("w0PatientId"); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-23
    const fileInput = document.getElementById("w0FileId");
    const questionInput = document.getElementById("w0Question");
    const scenarioInput = document.getElementById("w0Scenario");
    const cockpitBtn = document.getElementById("w0OpenCockpitBtn");
    const startBtn = document.getElementById("w0StartRunBtn");

    const patientId = Number(patientInput?.value || 0);
    const fileId = String(fileInput?.value || "").trim();
    const question = String(questionInput?.value || "").trim(); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-24
    const scenario = String(scenarioInput?.value || "happy_path").trim() || "happy_path";
    const availableModalities = getCheckedModalities();

    if (!Number.isFinite(patientId) || patientId <= 0) {
        updateHint("è¯·å¡«å†™æœ‰æ•ˆçš„ patient_idã€‚", true);
        return;
    }
    if (!fileId) {
        updateHint("è¯·å¡«å†™ file_idã€‚", true);
        return;
    }
    if (availableModalities.length === 0) {
        updateHint("è¯·è‡³å°‘é€‰æ‹©ä¸€ä¸ª modalityã€‚", true);
        return; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-25
    }

    startBtn.disabled = true;
    updateHint("æ­£åœ¨åˆ›å»º Mock run...");

    try {
        const payload = {
            patient_id: patientId,
            file_id: fileId,
            available_modalities: availableModalities,
            scenario,
        };
        if (question) payload.goal_question = question;

        const resp = await fetch("/api/strokeclaw/w0/mock-runs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await resp.json();
        if (!resp.ok || !data.success) {
            throw new Error(data.error || `åˆ›å»º Mock run å¤±è´¥ (${resp.status})`);
        }

        w0RunId = String(data.run_id || "").trim();
        w0PatientId = String(patientId);
        w0FileId = fileId; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-26

        if (w0FileId && w0RunId) {
            localStorage.setItem(`latest_w0_mock_run_${w0FileId}`, w0RunId);
        }

        if (cockpitBtn) cockpitBtn.disabled = !w0RunId;
        renderRun(data.run_state || {});
        updateHint(`Mock run å·²åˆ›å»ºï¼š${w0RunId}`);
        stopPolling();
        startPolling();
        await fetchRunAndEvents();
    } catch (err) {
        updateHint(`åˆ›å»º Mock run å¤±è´¥ï¼š${err.message}`, true);
    } finally {
        startBtn.disabled = false;
    }
}

function bindPageActions() {
    const startBtn = document.getElementById("w0StartRunBtn");
    const cockpitBtn = document.getElementById("w0OpenCockpitBtn"); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-27
    const uploadBtn = document.getElementById("w0GoUploadBtn");
    if (startBtn) {
        startBtn.addEventListener("click", startW0Run);
    }
    if (cockpitBtn) {
        cockpitBtn.addEventListener("click", () => {
            window.location.href = buildCockpitUrl();
        });
    }
    if (uploadBtn) {
        uploadBtn.addEventListener("click", () => {
            const patientInput = document.getElementById("w0PatientId");
            const patientId = Number(patientInput?.value || 0);
            if (Number.isFinite(patientId) && patientId > 0) {
                window.location.href = buildUploadUrl(patientId);
                return; // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-28
            }
            window.location.href = buildUploadUrl("");
        });
    }
}

function loadContextFromQuery() {
    const params = new URLSearchParams(window.location.search);
    const runId = String(params.get("run_id") || "").trim();
    const fileId = String(params.get("file_id") || "").trim();
    const patientId = String(params.get("patient_id") || "").trim();

    const patientInput = document.getElementById("w0PatientId");
    const fileInput = document.getElementById("w0FileId"); // AIè¾…åŠ©ç”Ÿæˆï¼šGLM-5, 2026-03-29
    const cockpitBtn = document.getElementById("w0OpenCockpitBtn");

    if (patientInput && patientId) patientInput.value = patientId;
    if (fileInput && fileId) fileInput.value = fileId;

    w0RunId = runId;
    w0FileId = fileId;
    w0PatientId = patientId;
    if (cockpitBtn) cockpitBtn.disabled = !w0RunId;

    if (w0RunId) {
        if (isMockRunId(w0RunId)) {
            updateHint(`å·²è½½å…¥ Mock run_idï¼š${w0RunId}`);
            startPolling();
            fetchRunAndEvents();
        } else {
            updateHint("æ£€æµ‹åˆ°çœŸå® run_idï¼ŒW0 è”è°ƒé¡µä»…å±•ç¤º Mock runï¼Œè¯·é‡æ–°å¯åŠ¨ Mock runã€‚", true);
            w0RunId = "";
            if (cockpitBtn) cockpitBtn.disabled = true;
        }
    }
}

document.addEventListener("DOMContentLoaded", () => {
    bindPageActions();
    loadContextFromQuery();
});
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   ™¢>oK>È¸”>më‰>êŠ>¥Œ>.€‰>–Bw>"ºg>Æås>w{„>!¾>ÍFš>E¸¢>§>«…¯>Ñrµ>aa°>íà©>µK¥>G™¥>]y¢>÷›>l>@¾‡>Z?‰>DÃ >d÷°>İu™>ïQo>—2k>h>ëÆq>'£>ÆÆ¶>¨.¬>§‰«>2j¤>sG–>²z>ÄøŒ>°©ˆ>)æ‚>9>[*ˆ>­>¬”>¬ó“>ÕK>e>z‚‰>¡~>¨Ni>B>ˆx*>	Ö>“%><;>OğK>leV>úJ[>$[`>fDg>Móo>æw>›¡z>ñxz>xVp>şm>(÷>Œ>«•>O. >„¥>õºš>jÓ‰>¨j†>m)‘>éÿ™>H°¤>cª¥>*“˜>ß%–>³qŸ>"=·>ÔM¾>ÿ"¶>¶
À>ÔÂĞ>aÃÕ>ÑÃ>cŠÀ>Ø¿>QT¿>ÿNµ>Ğ­> ¨>H°>sœÌ>ö&Ó>şÇ>ŒJ>«uE>B\8>UĞ>:îË=ƒ¦F>>&>[}4=Z“F=9B=ø B=SB=òOB=ëLB= MB=6MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=5MB=2MB=MB=¶MB=ûQB=‚*B=áÏA=‰íF=b¯K=¬Óš<¶“’>(K…>Êw>(x>¾b„>Œk€>1n>Z¨h>™x> ôz>Ù´j>®Ìx>M‘i>Öv_>(y>‰™>ŸœŠ>†$>6Èˆ>ÊÑ†>â->;¾”>8¦‹>J~‡>95“>¦î›>L=±>¼ÓÃ>IóÈ>"Â>Ê¡¾>oõ¥>%!>¿¦Š>×‹>è>ú|>¾š”>t}—>Wœ>ë0>í¦›>3›>M,›> ™>£–>§	> ¡>ˆœ>‰l’>@Š>î>Tç‹>Jç‹>Ÿ¢‰>j¤„>şõ>ó«„>„Œ>_–”>Ş…>}Ã£>$È¦>¤¦>:¡>T…Ÿ>_û>}¢>­F£>íß>Ş–>#‹><Q~>×V>]˜>êl…>_Gv>¤u>S‹t>Îæƒ>¦ö´>ÔÇ¹>\!©>¶¥>Q˜>¯—>¥ÂŒ>2T‹>+d‹>Û¾ˆ>İ‚>ƒ>òë>·h’>Iˆ“>xl>ÿ¥>^Ô‡>vÓw>ƒÛe>YyE>¿È)>Ã>Âğ >,Õ:>pM>W>Ê°[>æù^>.˜b>¢µg>c{i> ?b>
ÂY>"©V>o´a>}•s>Ã‰>“>B‰š>_—œ>µ¸>*B€>	]>$Œ>oe—>ç¡>å1¦>]">ëß–>˜›˜>¿Ÿ£>¹³>¤Î³>bŸ½>xÌ>š%Ğ>CüÏ>¯É>‚P»>^x±>­F­>sÌª>ìy¥>é >Ş¡ª>¥ú¾>£:¸>˜­>y„^>QnM>=³(>…¶>¥C>^Oæ=ƒ7=²ÉF=f4B=B=¬RB=¼OB=ğLB=!MB=6MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=2MB=3MB=SMB=ÅLB=lHB=ópB=ÚB=?==?ß8=îı²=óO”>´-x>p½|>~Áz>d>‡>™ˆ>Åâ„><­u>H|w>Ô{>ÆÉw>6S†>‰{^>6G*>®§f>üEš>Å’>}kŒ>³ƒ>¾\>%àŒ>¬y•>ìŒ>Í„>M‰>|ˆŠ>Š!>J¦œ>Ã¯>Š8­>œ>±«>·EŠ>Çˆ>ß_†>o2‹>cn>ïx”>AÜ•>â˜>9š>Û:š>€k›>/ï>÷ù˜>Z»“>~š>VÉ>•E™>Ct>ş1>4½’>±“>§o—>îæ—>ÂÏ–>e¡…>‚>˜IŒ>Ëƒ–>{f™>R¶™>¼òš>Æ›>ğÅ˜>‚À˜>i6™>ÖÑ>t£>ü >©ÿ—>Şõ>Y‚>—;€>úi€>m›y>}py> z>i³>õz”>©×À>5Î±>B>¢˜>•“>™á>6ÍŠ>‰>¾G‹>„¹‹>Cg†>Sy>éò‡>N>ÙZ”>‘>:ô‹>õß†>^Iw>9Ï_>?>üÄ%>A >Q°8>jíM>ì$X>ø]>–E^>š^>Õù_>U÷a> dc>±`>¶Y>®NY>Ê‡g>K{p>\§ƒ>·²>–>S¾‘>K±…>S|>«|>­š…> Š‘>)œ>M€¤>ĞÉ¡>¾–>yx”>şU”>Šy>L©>¸¸>%/Ë>(Ê>³Jº>øµ²>A¬>t?¦>[Ğ¥>`Ò¥>`® >¸ƒ—>b‘’>d¥>Zÿ­>/p‚>Å4v>]z>~Km>RqX>8K>Õ>Ü=uk6=jG=8.B=®ÿA=(SB=éOB=ìLB=!MB=6MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=3MB=…c–    ï\ï\ï\           À x  Æ          7 Æ      Á k b _ m a n i f e s t . j s o Á n                             …T”    ï\ï\ï\           À h  <µS         B <µS     Á -NıVRS-N2–»lcü[Ä‰ƒ. p d f                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 …Ç-   ï\ï\ï\¸¸          À 5             9        Á r e a c t                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     /**
 * @license React
 * react-dom.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
(function(){/*
 Modernizr 3.0.0pre (Custom Build) | MIT
*/
'use strict';(function(Q,zb){"object"===typeof exports&&"undefined"!==typeof module?zb(exports,require("react")):"function"===typeof define&&define.amd?define(["exports","react"],zb):(Q=Q||self,zb(Q.ReactDOM={},Q.React))})(this,function(Q,zb){function m(a){for(var b="https://reactjs.org/docs/error-decoder.html?invariant="+a,c=1;c<arguments.length;c++)b+="&args[]="+encodeURIComponent(arguments[c]);return"Minified React error #"+a+"; visit "+b+" for the full message or use the non-minified dev environment for full errors and additional helpful warnings."}
function mb(a,b){Ab(a,b);Ab(a+"Capture",b)}function Ab(a,b){$b[a]=b;for(a=0;a<b.length;a++)cg.add(b[a])}function bj(a){if(Zd.call(dg,a))return!0;if(Zd.call(eg,a))return!1;if(cj.test(a))return dg[a]=!0;eg[a]=!0;return!1}function dj(a,b,c,d){if(null!==c&&0===c.type)return!1;switch(typeof b){case "function":case "symbol":return!0;case "boolean":if(d)return!1;if(null!==c)return!c.acceptsBooleans;a=a.toLowerCase().slice(0,5);return"data-"!==a&&"aria-"!==a;default:return!1}}function ej(a,b,c,d){if(null===
b||"undefined"===typeof b||dj(a,b,c,d))return!0;if(d)return!1;if(null!==c)switch(c.type){case 3:return!b;case 4:return!1===b;case 5:return isNaN(b);case 6:return isNaN(b)||1>b}return!1}function Y(a,b,c,d,e,f,g){this.acceptsBooleans=2===b||3===b||4===b;this.attributeName=d;this.attributeNamespace=e;this.mustUseProperty=c;this.propertyName=a;this.type=b;this.sanitizeURL=f;this.removeEmptyString=g}function $d(a,b,c,d){var e=R.hasOwnProperty(b)?R[b]:null;if(null!==e?0!==e.type:d||!(2<b.length)||"o"!==
b[0]&&"O"!==b[0]||"n"!==b[1]&&"N"!==b[1])ej(b,c,e,d)&&(c=null),d||null===e?bj(b)&&(null===c?a.removeAttribute(b):a.setAttribute(b,""+c)):e.mustUseProperty?a[e.propertyName]=null===c?3===e.type?!1:"":c:(b=e.attributeName,d=e.attributeNamespace,null===c?a.removeAttribute(b):(e=e.type,c=3===e||4===e&&!0===c?"":""+c,d?a.setAttributeNS(d,b,c):a.setAttribute(b,c)))}function ac(a){if(null===a||"object"!==typeof a)return null;a=fg&&a[fg]||a["@@iterator"];return"function"===typeof a?a:null}function bc(a,b,
c){if(void 0===ae)try{throw Error();}catch(d){ae=(b=d.stack.trim().match(/\n( *(at )?)/))&&b[1]||""}return"\n"+ae+a}function be(a,b){if(!a||ce)return"";ce=!0;var c=Error.prepareStackTrace;Error.prepareStackTrace=void 0;try{if(b)if(b=function(){throw Error();},Object.defineProperty(b.prototype,"props",{set:function(){throw Error();}}),"object"===typeof Reflect&&Reflect.construct){try{Reflect.construct(b,[])}catch(n){var d=n}Reflect.construct(a,[],b)}else{try{b.call()}catch(n){d=n}a.call(b.prototype)}else{try{throw Error();
}catch(n){d=n}a()}}catch(n){if(n&&d&&"string"===typeof n.stack){for(var e=n.stack.split("\n"),f=d.stack.split("\n"),g=e.length-1,h=f.length-1;1<=g&&0<=h&&e[g]!==f[h];)h--;for(;1<=g&&0<=h;g--,h--)if(e[g]!==f[h]){if(1!==g||1!==h){do if(g--,h--,0>h||e[g]!==f[h]){var k="\n"+e[g].replace(" at new "," at ");a.displayName&&k.includes("<anonymous>")&&(k=k.replace("<anonymous>",a.displayName));return k}while(1<=g&&0<=h)}break}}}finally{ce=!1,Error.prepareStackTrace=c}return(a=a?a.displayName||a.name:"")?bc(a):
""}function fj(a){switch(a.tag){case 5:return bc(a.type);case 16:return bc("Lazy");case 13:return bc("Suspense");case 19:return bc("SuspenseList");case 0:case 2:case 15:return a=be(a.type,!1),a;case 11:return a=be(a.type.render,!1),a;case 1:return a=be(a.type,!0),a;default:return""}}function de(a){if(null==a)return null;if("function"===typeof a)return a.displayName||a.name||null;if("string"===typeof a)return a;switch(a){case Bb:return"Fragment";case Cb:return"Portal";case ee:return"Profiler";case fe:return"StrictMode";
case ge:return"Suspense";case he:return"SuspenseList"}if("object"===typeof a)switch(a.$$typeof){case gg:return(a.displayName||"Context")+".Consumer";case hg:return(a._context.displayName||"Context")+".Provider";case ie:var b=a.render;a=a.displayName;a||(a=b.displayName||b.name||"",a=""!==a?"ForwardRef("+a+")":"ForwardRef");return a;case je:return b=a.displayName||null,null!==b?b:de(a.type)||"Memo";case Ta:b=a._payload;a=a._init;try{return de(a(b))}catch(c){}}return null}function gj(a){var b=a.type;
switch(a.tag){case 24:return"Cache";case 9:return(b.displayName||"Context")+".Consumer";case 10:return(b._context.displayName||"Context")+".Provider";case 18:return"DehydratedFragment";case 11:return a=b.render,a=a.displayName||a.name||"",b.displayName||(""!==a?"ForwardRef("+a+")":"ForwardRef");case 7:return"Fragment";case 5:return b;case 4:return"Portal";case 3:return"Root";case 6:return"Text";case 16:return de(b);case 8:return b===fe?"StrictMode":"Mode";case 22:return"Offscreen";case 12:return"Profiler";
case 21:return"Scope";case 13:return"Suspense";case 19:return"SuspenseList";case 25:return"TracingMarker";case 1:case 0:case 17:case 2:case 14:case 15:if("function"===typeof b)return b.displayName||b.name||null;if("string"===typeof b)return b}return null}function Ua(a){switch(typeof a){case "boolean":case "number":case "string":case "undefined":return a;case "object":return a;default:return""}}function ig(a){var b=a.type;return(a=a.nodeName)&&"input"===a.toLowerCase()&&("checkbox"===b||"radio"===
b)}function hj(a){var b=ig(a)?"checked":"value",c=Object.getOwnPropertyDescriptor(a.constructor.prototype,b),d=""+a[b];if(!a.hasOwnProperty(b)&&"undefined"!==typeof c&&"function"===typeof c.get&&"function"===typeof c.set){var e=c.get,f=c.set;Object.defineProperty(a,b,{configurable:!0,get:function(){return e.call(this)},set:function(a){d=""+a;f.call(this,a)}});Object.defineProperty(a,b,{enumerable:c.enumerable});return{getValue:function(){return d},setValue:function(a){d=""+a},stopTracking:function(){a._valueTracker=
null;delete a[b]}}}}function Pc(a){a._valueTracker||(a._valueTracker=hj(a))}function jg(a){if(!a)return!1;var b=a._valueTracker;if(!b)return!0;var c=b.getValue();var d="";a&&(d=ig(a)?a.checked?"true":"false":a.value);a=d;return a!==c?(b.setValue(a),!0):!1}function Qc(a){a=a||("undefined"!==typeof document?document:void 0);if("undefined"===typeof a)return null;try{return a.activeElement||a.body}catch(b){return a.body}}function ke(a,b){var c=b.checked;return E({},b,{defaultChecked:void 0,defaultValue:void 0,
value:void 0,checked:null!=c?c:a._wrapperState.initialChecked})}function kg(a,b){var c=null==b.defaultValue?"":b.defaultValue,d=null!=b.checked?b.checked:b.defaultChecked;c=Ua(null!=b.value?b.value:c);a._wrapperState={initialChecked:d,initialValue:c,controlled:"checkbox"===b.type||"radio"===b.type?null!=b.checked:null!=b.value}}function lg(a,b){b=b.checked;null!=b&&$d(a,"checked",b,!1)}function le(a,b){lg(a,b);var c=Ua(b.value),d=b.type;if(null!=c)if("number"===d){if(0===c&&""===a.value||a.value!=
c)a.value=""+c}else a.value!==""+c&&(a.value=""+c);else if("submit"===d||"reset"===d){a.removeAttribute("value");return}b.hasOwnProperty("value")?me(a,b.type,c):b.hasOwnProperty("defaultValue")&&me(a,b.type,Ua(b.defaultValue));null==b.checked&&null!=b.defaultChecked&&(a.defaultChecked=!!b.defaultChecked)}function mg(a,b,c){if(b.hasOwnProperty("value")||b.hasOwnProperty("defaultValue")){var d=b.type;if(!("submit"!==d&&"reset"!==d||void 0!==b.value&&null!==b.value))return;b=""+a._wrapperState.initialValue;
c||b===a.value||(a.value=b);a.defaultValue=b}c=a.name;""!==c&&(a.name="");a.defaultChecked=!!a._wrapperState.initialChecked;""!==c&&(a.name=c)}function me(a,b,c){if("number"!==b||Qc(a.ownerDocument)!==a)null==c?a.defaultValue=""+a._wrapperState.initialValue:a.defaultValue!==""+c&&(a.defaultValue=""+c)}function Db(a,b,c,d){a=a.options;if(b){b={};for(var e=0;e<c.length;e++)b["$"+c[e]]=!0;for(c=0;c<a.length;c++)e=b.hasOwnProperty("$"+a[c].value),a[c].selected!==e&&(a[c].selected=e),e&&d&&(a[c].defaultSelected=
!0)}else{c=""+Ua(c);b=null;for(e=0;e<a.length;e++){if(a[e].value===c){a[e].selected=!0;d&&(a[e].defaultSelected=!0);return}null!==b||a[e].disabled||(b=a[e])}null!==b&&(b.selected=!0)}}function ne(a,b){if(null!=b.dangerouslySetInnerHTML)throw Error(m(91));return E({},b,{value:void 0,defaultValue:void 0,children:""+a._wrapperState.initialValue})}function ng(a,b){var c=b.value;if(null==c){c=b.children;b=b.defaultValue;if(null!=c){if(null!=b)throw Error(m(92));if(cc(c)){if(1<c.length)throw Error(m(93));
c=c[0]}b=c}null==b&&(b="");c=b}a._wrapperState={initialValue:Ua(c)}}function og(a,b){var c=Ua(b.value),d=Ua(b.defaultValue);null!=c&&(c=""+c,c!==a.value&&(a.value=c),null==b.defaultValue&&a.defaultValue!==c&&(a.defaultValue=c));null!=d&&(a.defaultValue=""+d)}function pg(a,b){b=a.textContent;b===a._wrapperState.initialValue&&""!==b&&null!==b&&(a.value=b)}function qg(a){switch(a){case "svg":return"http://www.w3.org/2000/svg";case "math":return"http://www.w3.org/1998/Math/MathML";default:return"http://www.w3.org/1999/xhtml"}}
function oe(a,b){return null==a||"http://www.w3.org/1999/xhtml"===a?qg(b):"http://www.w3.org/2000/svg"===a&&"foreignObject"===b?"http://www.w3.org/1999/xhtml":a}function rg(a,b,c){return null==b||"boolean"===typeof b||""===b?"":c||"number"!==typeof b||0===b||dc.hasOwnProperty(a)&&dc[a]?(""+b).trim():b+"px"}function sg(a,b){a=a.style;for(var c in b)if(b.hasOwnProperty(c)){var d=0===c.indexOf("--"),e=rg(c,b[c],d);"float"===c&&(c="cssFloat");d?a.setProperty(c,e):a[c]=e}}function pe(a,b){if(b){if(ij[a]&&
(null!=b.children||null!=b.dangerouslySetInnerHTML))throw Error(m(137,a));if(null!=b.dangerouslySetInnerHTML){if(null!=b.children)throw Error(m(60));if("object"!==typeof b.dangerouslySetInnerHTML||!("__html"in b.dangerouslySetInnerHTML))throw Error(m(61));}if(null!=b.style&&"object"!==typeof b.style)throw Error(m(62));}}function qe(a,b){if(-1===a.indexOf("-"))return"string"===typeof b.is;switch(a){case "annotation-xml":case "color-profile":case "font-face":case "font-face-src":case "font-face-uri":case "font-face-format":case "font-face-name":case "missing-glyph":return!1;
default:return!0}}function re(a){a=a.target||a.srcElement||window;a.correspondingUseElement&&(a=a.correspondingUseElement);return 3===a.nodeType?a.parentNode:a}function tg(a){if(a=ec(a)){if("function"!==typeof se)throw Error(m(280));var b=a.stateNode;b&&(b=Rc(b),se(a.stateNode,a.type,b))}}function ug(a){Eb?Fb?Fb.push(a):Fb=[a]:Eb=a}function vg(){if(Eb){var a=Eb,b=Fb;Fb=Eb=null;tg(a);if(b)for(a=0;a<b.length;a++)tg(b[a])}}function wg(a,b,c){if(te)return a(b,c);te=!0;try{return xg(a,b,c)}finally{if(te=
!1,null!==Eb||null!==Fb)yg(),vg()}}function fc(a,b){var c=a.stateNode;if(null===c)return null;var d=Rc(c);if(null===d)return null;c=d[b];a:switch(b){case "onClick":case "onClickCapture":case "onDoubleClick":case "onDoubleClickCapture":case "onMouseDown":case "onMouseDownCapture":case "onMouseMove":case "onMouseMoveCapture":case "onMouseUp":case "onMouseUpCapture":case "onMouseEnter":(d=!d.disabled)||(a=a.type,d=!("button"===a||"input"===a||"select"===a||"textarea"===a));a=!d;break a;default:a=!1}if(a)return null;
if(c&&"function"!==typeof c)throw Error(m(231,b,typeof c));return c}function jj(a,b,c,d,e,f,g,h,k){gc=!1;Sc=null;kj.apply(lj,arguments)}function mj(a,b,c,d,e,f,g,h,k){jj.apply(this,arguments);if(gc){if(gc){var n=Sc;gc=!1;Sc=null}else throw Error(m(198));Tc||(Tc=!0,ue=n)}}function nb(a){var b=a,c=a;if(a.alternate)for(;b.return;)b=b.return;else{a=b;do b=a,0!==(b.flags&4098)&&(c=b.return),a=b.return;while(a)}return 3===b.tag?c:null}function zg(a){if(13===a.tag){var b=a.memoizedState;null===b&&(a=a.alternate,
null!==a&&(b=a.memoizedState));if(null!==b)return b.dehydrated}return null}function Ag(a){if(nb(a)!==a)throw Error(m(188));}function nj(a){var b=a.alternate;if(!b){b=nb(a);if(null===b)throw Error(m(188));return b!==a?null:a}for(var c=a,d=b;;){var e=c.return;if(null===e)break;var f=e.alternate;if(null===f){d=e.return;if(null!==d){c=d;continue}break}if(e.child===f.child){for(f=e.child;f;){if(f===c)return Ag(e),a;if(f===d)return Ag(e),b;f=f.sibling}throw Error(m(188));}if(c.return!==d.return)c=e,d=f;
else{for(var g=!1,h=e.child;h;){if(h===c){g=!0;c=e;d=f;break}if(h===d){g=!0;d=e;c=f;break}h=h.sibling}if(!g){for(h=f.child;h;){if(h===c){g=!0;c=f;d=e;break}if(h===d){g=!0;d=f;c=e;break}h=h.sibling}if(!g)throw Error(m(189));}}if(c.alternate!==d)throw Error(m(190));}if(3!==c.tag)throw Error(m(188));return c.stateNode.current===c?a:b}function Bg(a){a=nj(a);return null!==a?Cg(a):null}function Cg(a){if(5===a.tag||6===a.tag)return a;for(a=a.child;null!==a;){var b=Cg(a);if(null!==b)return b;a=a.sibling}return null}
function oj(a,b){if(Ca&&"function"===typeof Ca.onCommitFiberRoot)try{Ca.onCommitFiberRoot(Uc,a,void 0,128===(a.current.flags&128))}catch(c){}}function pj(a){a>>>=0;return 0===a?32:31-(qj(a)/rj|0)|0}function hc(a){switch(a&-a){case 1:return 1;case 2:return 2;case 4:return 4;case 8:return 8;case 16:return 16;case 32:return 32;case 64:case 128:case 256:case 512:case 1024:case 2048:case 4096:case 8192:case 16384:case 32768:case 65536:case 131072:case 262144:case 524288:case 1048576:case 2097152:return a&
4194240;case 4194304:case 8388608:case 16777216:case 33554432:case 67108864:return a&130023424;case 134217728:return 134217728;case 268435456:return 268435456;case 536870912:return 536870912;case 1073741824:return 1073741824;default:return a}}function Vc(a,b){var c=a.pendingLanes;if(0===c)return 0;var d=0,e=a.suspendedLanes,f=a.pingedLanes,g=c&268435455;if(0!==g){var h=g&~e;0!==h?d=hc(h):(f&=g,0!==f&&(d=hc(f)))}else g=c&~e,0!==g?d=hc(g):0!==f&&(d=hc(f));if(0===d)return 0;if(0!==b&&b!==d&&0===(b&e)&&
(e=d&-d,f=b&-b,e>=f||16===e&&0!==(f&4194240)))return b;0!==(d&4)&&(d|=c&16);b=a.entangledLanes;if(0!==b)for(a=a.entanglements,b&=d;0<b;)c=31-ta(b),e=1<<c,d|=a[c],b&=~e;return d}function sj(a,b){switch(a){case 1:case 2:case 4:return b+250;case 8:case 16:case 32:case 64:case 128:case 256:case 512:case 1024:case 2048:case 4096:case 8192:case 16384:case 32768:case 65536:case 131072:case 262144:case 524288:case 1048576:case 2097152:return b+5E3;case 4194304:case 8388608:case 16777216:case 33554432:case 67108864:return-1;
case 134217728:case 268435456:case 536870912:case 1073741824:return-1;default:return-1}}function tj(a,b){for(var c=a.suspendedLanes,d=a.pingedLanes,e=a.expirationTimes,f=a.pendingLanes;0<f;){var g=31-ta(f),h=1<<g,k=e[g];if(-1===k){if(0===(h&c)||0!==(h&d))e[g]=sj(h,b)}else k<=b&&(a.expiredLanes|=h);f&=~h}}function ve(a){a=a.pendingLanes&-1073741825;return 0!==a?a:a&1073741824?1073741824:0}function Dg(){var a=Wc;Wc<<=1;0===(Wc&4194240)&&(Wc=64);return a}function we(a){for(var b=[],c=0;31>c;c++)b.push(a);
return b}function ic(a,b,c){a.pendingLanes|=b;536870912!==b&&(a.suspendedLanes=0,a.pingedLanes=0);a=a.eventTimes;b=31-ta(b);a[b]=c}function uj(a,b){var c=a.pendingLanes&~b;a.pendingLanes=b;a.suspendedLanes=0;a.pingedLanes=0;a.expiredLanes&=b;a.mutableReadLanes&=b;a.entangledLanes&=b;b=a.entanglements;var d=a.eventTimes;for(a=a.expirationTimes;0<c;){var e=31-ta(c),f=1<<e;b[e]=0;d[e]=-1;a[e]=-1;c&=~f}}function xe(a,b){var c=a.entangledLanes|=b;for(a=a.entanglements;c;){var d=31-ta(c),e=1<<d;e&b|a[d]&
b&&(a[d]|=b);c&=~e}}function Eg(a){a&=-a;return 1<a?4<a?0!==(a&268435455)?16:536870912:4:1}function Fg(a,b){switch(a){case "focusin":case "focusout":Va=null;break;case "dragenter":case "dragleave":Wa=null;break;case "mouseover":case "mouseout":Xa=null;break;case "pointerover":case "pointerout":jc.delete(b.pointerId);break;case "gotpointercapture":case "lostpointercapture":kc.delete(b.pointerId)}}function lc(a,b,c,d,e,f){if(null===a||a.nativeEvent!==f)return a={blockedOn:b,domEventName:c,eventSystemFlags:d,
nativeEvent:f,targetContainers:[e]},null!==b&&(b=ec(b),null!==b&&Gg(b)),a;a.eventSystemFlags|=d;b=a.targetContainers;null!==e&&-1===b.indexOf(e)&&b.push(e);return a}function vj(a,b,c,d,e){switch(b){case "focusin":return Va=lc(Va,a,b,c,d,e),!0;case "dragenter":return Wa=lc(Wa,a,b,c,d,e),!0;case "mouseover":return Xa=lc(Xa,a,b,c,d,e),!0;case "pointerover":var f=e.pointerId;jc.set(f,lc(jc.get(f)||null,a,b,c,d,e));return!0;case "gotpointercapture":return f=e.pointerId,kc.set(f,lc(kc.get(f)||null,a,b,
c,d,e)),!0}return!1}function Hg(a){var b=ob(a.target);if(null!==b){var c=nb(b);if(null!==c)if(b=c.tag…s—    ï\ï\ï\Å           À ·Å  ö           m ö       Á c o n f t e s t . p y         …RÍ   ï\ï\ï\ÆÆ          À 2À             n        Á j s                           …×D    ï\ï\ï\	           À oÓ  ©          r ©      Á r u n _ i c v _ s m o k e . p Á y                             …—d    ï\ï\ï\           À %X  ×	          s ×	      Á t e s t _ a g e n t _ l o o p Á _ m o d u l e s . p y         …hE    ï\ï\ï\           À Kl  >          t >      Á t e s t _ c h a t _ p a t i e Á n t _ i d _ c o m m a n d . p Á y                             …öé    ï\ï\ï\           À ›  P          u P      Á t e s t _ c o m p a t _ r o u Á t e s _ c o n t r a c t . p y …#Å    ï\ï\ï\           À {Í  Î          v Î      Á t e s t _ d i n o v 3 _ a d a Á p t e r . p y                 …#    ï\ï\ï\           À -  ä          w ä      Á t e s t _ e k v . p y         …š     ï\ï\ï\           À ñ`  ì          x ì      Á t e s t _ e k v _ r e t r i e Á v a l _ w e i g h t i n g . p Á y                             …ö×    ï\ï\ï\           À c¤             y        Á t e s t _ f i e l d _ c o m p Á a t _ a d a p t e r s . p y   …Ì    ï\ï\ï\           À ­Š  t	          z t	      Á t e s t _ i c v . p y         …-†    ï\ï\ï\            À ¥M  ÷          { ÷      Á t e s t _ i c v _ m o r e . p Á y                             …ıU    ï\ï\ï\"           À í  ü          | ü      Á t e s t _ i c v _ r u l e s . Á p y                           …¡7    ï\ï\ï\#           À ·!  É          } É      Á t e s t _ k b _ r o u t e s _ Á c o n t r a c t . p y         …Uß    ï\ï\ï\%           À Â"  “          ~ “      Á t e s t _ s t a t i c _ j s _ Á s y n t a x . p y             …E    ï\ï\ï\&           À  0  ¤           ¤      Á t e s t _ v e s s e l _ a g e Á n t _ p r o p a g a t i o n . Á p y                           …u*    ï\ï\ï\(           À „Ã  ¡          € ¡      Á t e s t _ v e s s e l _ c o n Á t e x t . p y                 …µø    ï\ï\ï\*           À FR  È'           È'      Á t e s t _ v e s s e l _ p i p Á e l i n e . p y               …¼7   Ä	ï\Ä	ï\Ä	ï\´´          À ß             Œ        Á _ _ p y c a c h e _ _         …Ú—    m
ï\†
ï\†
ï\:           À ¬
  AJ           AJ      Á t e s t _ i m a g e _ q c . p Á y                             …nø    ©ï\ï\ï\‡           À !ˆ            ³       Á t e s t _ q c _ p e r s i s t Á e n c e _ a n d _ r e v i e w Á . p y                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             