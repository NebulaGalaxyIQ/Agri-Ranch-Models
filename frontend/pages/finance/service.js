import {get,post} from '../../shared/api.js';export const entries=()=>get('v5/finance');export const summary=()=>get('v5/finance/profit-summary');export const add=d=>post('v5/finance',d);
