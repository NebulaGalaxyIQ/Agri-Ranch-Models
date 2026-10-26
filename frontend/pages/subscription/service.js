import {get,post} from '../../shared/api.js';
export const details=()=>get('cape/subscription/status');
export const requestPlan=data=>post('cape/subscription/request',data);
export const activateTrial=()=>post('cape/subscription/trial/start',{});
export const redeemKey=data=>post('v5/subscription/redeem',data);
export const requests=()=>get('cape/subscription/requests');
