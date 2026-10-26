import {get,post,put,patch} from '../../shared/api.js';
export const organizations=()=>get('v5/platform/organizations');export const insights=()=>get('v5/platform/insights');export const support=()=>get('v5/platform/help/tickets');export const detail=id=>get(`v5/platform/organization-detail/${id}`);

export const offers=()=>get('v6/platform/offers');
export const createOffer=async data=>(await import('../../shared/api.js')).post('v6/platform/offers',data);
export const updateOffer=async(id,active)=>(await import('../../shared/api.js')).patch(`v6/platform/offers/${id}?active=${active}`,{});
