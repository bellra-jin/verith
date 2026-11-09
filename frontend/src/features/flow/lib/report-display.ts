// Presentation only. Never replace a missing observation with measured zero.
export const ZERO_LIMIT_NOTICE='저장된 강도 0은 분모 미확인에 따른 후퇴값일 수 있어 측정된 0%나 중립을 보증하지 않습니다.';
export const STRENGTH_NOTICE='최근 실제 관측 N행 순매수합 ÷ 같은 창의 일평균 거래대금입니다. 전체 기간 거래대금 비중·보유율이 아니며 100%를 넘을 수 있습니다.';
export const displayFinite=(value:unknown):value is number=>typeof value==='number'&&Number.isFinite(value);
// Exact binary64 rational rounded to nearest, ties-to-even, as Python's f-string.
function roundedMagnitude(value:number,precision:number):string{
 const view=new DataView(new ArrayBuffer(8));view.setFloat64(0,Math.abs(value),false);
 const bits=(BigInt(view.getUint32(0))<<BigInt(32))|BigInt(view.getUint32(4)),exponent=Number((bits>>BigInt(52))&BigInt(2047));
 const fraction=bits&((BigInt(1)<<BigInt(52))-BigInt(1)),mantissa=exponent===0?fraction:(BigInt(1)<<BigInt(52))|fraction,power=exponent===0?-1074:exponent-1075;
 let numerator=mantissa*BigInt(10)**BigInt(precision),denominator=BigInt(1);
 if(power>=0)numerator<<=BigInt(power);else denominator<<=BigInt(-power);
 let rounded=numerator/denominator;const remainder=numerator%denominator;
 if(remainder*BigInt(2)>denominator||remainder*BigInt(2)===denominator&&rounded%BigInt(2)===BigInt(1))rounded++;
 const digits=rounded.toString().padStart(precision+1,'0');
 return BigInt(precision?digits.slice(0,-precision):digits).toLocaleString('ko-KR')+(precision?'.'+digits.slice(-precision):'');
}
export function displayNumber(value:unknown,precision=0,unit='',scale=1,signed=true):string{
 if(!displayFinite(value))return '자료 없음';
 const nonzero=value!==0,positive=value>0,shown=value*scale;
 if(!Number.isFinite(shown))return '표시 범위 초과';
 const text=roundedMagnitude(shown,precision);
 if(nonzero&&(shown===0||Number(text.replaceAll(',',''))===0))return `${positive?'양수':'음수'}·표시 정밀도 미만(${unit})`;
 return `${shown<0?'-':signed&&shown>0?'+':''}${text}${unit}`;
}
export function displayDirection(value:unknown):'매수'|'매도'|'중립'|'판단 보류'{return !displayFinite(value)?'판단 보류':value>0?'매수':value<0?'매도':'중립';}
export function gaugeVerdict(fore:unknown,inst:unknown):'매수 우위'|'매도 우위'|'중립'|'판단 보류'{
 if(!displayFinite(fore)||!displayFinite(inst)||!Number.isFinite(fore+inst))return '판단 보류';
 return fore+inst>0?'매수 우위':fore+inst<0?'매도 우위':'중립';
}
export function institutionLeader(shown:ReadonlyArray<readonly [string,unknown]>):string|null{
 const values=shown.filter((v):v is readonly [string,number]=>displayFinite(v[1])).slice().sort((a,b)=>b[1]-a[1]);
 if(!values.length)return null;
 return values[0][1]>0?`${values[0][0]} 주도`:values[0][1]===0?'표시된 세부 중 순매수 없음(0 포함)':'표시된 세부 값은 모두 순매도';
}

export function displayArrow(value:unknown):string{return !displayFinite(value)?'':value>0?'▲ ':value<0?'▼ ':'― ';}
