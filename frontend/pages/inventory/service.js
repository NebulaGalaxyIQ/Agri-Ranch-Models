import {get,post} from '../../shared/api.js';
export const stock=()=>get('v5/stock/status');export const ledger=()=>get('v5/stock/ledger');export const register=d=>post('v5/stock/items',d);export const receive=d=>post('v5/stock/receive',d);export const issue=d=>post('v5/stock/issue',d);
