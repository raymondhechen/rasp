from nexus.module import Module, Spike, RunManager
from nexus.store import ObjectNotFoundError
from queue import Empty
from scipy.sparse import csc_matrix
from skimage.measure import find_contours
import numpy as np
import time
import cv2
import colorsys

import logging; logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class Analysis(Module):
    '''Abstract class for the analysis module
    Performs additional computations on the extracted
    neural activity from the processor module
    '''
    #def putAnalysis(self):
    #    # Update the DS with analysis
    #    raise NotImplementedError


class MeanAnalysis(Analysis):
    def __init__(self, *args):
        super().__init__(*args)

    def setup(self, param_file=None):
        '''
        '''
        # TODO: same as behaviorAcquisition, need number of stimuli here. TODO: make adaptive later
        self.num_stim = 21 
        self.frame = 0
        self.flag = False
        self.curr_stim = 0 #start with zeroth stim unless signaled otherwise
        self.stimInd = []
        self.onoff = []
        self.window = 200 #TODO: make user input, choose scrolling window for Visual
        self.A = None
        self.C = None
        self.Call = None
        self.Cx = None
        self.Cpop = None
        self.coords = None
        self.updateCoordsTime = []
        self.color = None

    def run(self):
        self.total_times = []
        self.puttime = []
        self.colortime = []
        self.stimtime = []

        with RunManager(self.name, self.runAvg, self.setup, self.q_sig, self.q_comm) as rm:
            logger.info(rm)
        # ests structure: np.array([components, frames])
        # while True:
        #     t = time.time()
        #     if self.flag:
        #         try:
        #             self.runAvg()
        #             if self.done:
        #                 logger.info('Analysis is done, exiting')
        #                 return
        #         except Exception as e:
        #             logger.error('Analysis exception during run: {}'.format(e))
        #             break 
        #     try: 
        #         signal = self.q_sig.get(timeout=0.005)
        #         if signal == Spike.run(): 
        #             self.flag = True
        #             logger.warning('Received run signal, begin running')
        #         elif signal == Spike.quit():
        #             logger.warning('Received quit signal, aborting')
        #             break    
        #         elif signal == Spike.pause():
        #             logger.warning('Received pause signal, pending...')
        #             self.flag = False
        #         elif signal == Spike.resume(): #currently treat as same as run
        #             logger.warning('Received resume signal, resuming')
        #             self.flag = True 
        #     except Empty as e:
        #         pass #no signal from Nexus
        #     try: 
        #         sig = self.links['input_stim_queue'].get(timeout=0.005)
        #         self.updateStim(sig)
        #     except Empty as e:
        #         pass #no change in input stimulus
        #         #TODO: other errors
                    
        #     total_times.append(time.time()-t)
        print('Analysis broke, avg time per frame: ', np.mean(self.total_times))
        print('Analysis broke, avg time per put analysis: ', np.mean(self.puttime))
        print('Analysis broke, avg time per color frame: ', np.mean(self.colortime))
        print('Analysis broke, avg time per stim avg: ', np.mean(self.stimtime))
        print('Analysis got through ', self.frame, ' frames')


    def runAvg(self):
        ''' Take numpy estimates and frame_number
            Create X and Y for plotting
        '''
        t = time.time()
        try: 
            sig = self.links['input_stim_queue'].get(timeout=0.0001)
            self.updateStim(sig)
        except Empty as e:
            pass #no change in input stimulus
            #TODO: other errors
        try:
            #TODO: add error handling for if we received some but not all of these
            ids = self.q_in.get(timeout=0.0001)
            # res = []
            # for id in ids:
            #     res.append(self.client.getID(id))
            (self.C, self.coordDict, self.image) = self.client.getList(ids) #res

            self.coords = [o['coordinates'] for o in self.coordDict]

            # Keep internal running count 
            # self.frame += 1 #DANGER
            self.frame = self.C.shape[1]
            # From the input_stim_queue update the current stimulus (once per frame)
            #DANGER FIXME TODO Use a timestamp here
            self.stimInd.append(self.curr_stim)
            self.onoff.append(self.onoff_stim)
            
            # Compute tuning curves based on input stimulus
            # Just do overall average activity for now
            self.tuning_all = self.stimAvg(self.C)
            self.globalAvg = np.mean(self.tuning_all, axis=0)
            self.tune = [self.tuning_all, self.globalAvg]

            # Compute coloring of neurons for processed frame
            # Also rotate and stack as needed for plotting
            if self.frame % 2 == 0: #TODO: move to viz, but we don't need to compute this 30 times/sec
                self.color = self.plotColorFrame()

            if self.frame >= self.window:
                window = self.window
            else:
                window = self.frame

            if self.C.shape[1]>0:
                self.Cpop = np.nanmean(self.C[:,self.frame-window:self.frame], axis=0)
                self.Cx = np.arange(0,self.Cpop.size)+(self.frame-window)
                self.Call = self.C[:,self.frame-window:self.frame]
            
            self.putAnalysis()
            self.total_times.append(time.time()-t)
        except ObjectNotFoundError:
            logger.error('Estimates unavailable from store, droppping')
        except Empty as e:
            pass
        except Exception as e:
            logger.exception('Error in analysis: {}'.format(e))

    def updateStim(self, stim):
        ''' Recevied new signal from Behavior Acquirer to change input stimulus
            [possibly other action items here...? Validation?]
        '''
        # stim in format n:value
        #print('stim---------------: ', stim[0][1])
        if(self.curr_stim != stim[0][0]):
            logger.info('Changed stimulus: '+str(stim[0][0]))
        self.curr_stim = stim[0][0]
        self.onoff_stim = (1 if abs(stim[0][1]) > 1 else 0)

    def putAnalysis(self):
        ''' Throw things to DS and put IDs in queue for Visual
        '''
        t = time.time()
        ids = []
        ids.append(self.client.put(self.Cx, 'Cx'+str(self.frame)))
        ids.append(self.client.put(self.Call, 'Call'+str(self.frame)))
        ids.append(self.client.put(self.Cpop, 'Cpop'+str(self.frame)))
        ids.append(self.client.put(self.tune, 'tune'+str(self.frame)))
        #ids.append(self.client.put(self.raw, 'raw'+str(self.frame)))
        ids.append(self.client.put(self.color, 'color'+str(self.frame)))
        ids.append(self.client.put(self.coordDict, 'coords'+str(self.frame)))

        self.q_out.put(ids)
        #print('time put analysis: ', time.time()-t)
        self.puttime.append(time.time()-t)
        #self.q_comm.put([self.frame])

    def stimAvg(self, ests):
        ''' Using stimInd as mask, average ests across each input stimulus
        '''
        t = time.time()
        estsAvg = []
        stimInd = np.array(self.stimInd[:ests.shape[1]])
        onoff = np.array(self.onoff[:ests.shape[1]])
        on = np.where(onoff==1, 1, np.nan)
        off = np.where(onoff==0, 1, np.nan)
        for j in range(0, self.num_stim):
            #tmp = np.nanmean(np.where(stimInd==j, ests, np.nan), axis=1)
            tmpEsts = np.where(stimInd==j, ests, np.nan)
            tmpOn = np.where(stimInd==j, on, np.nan)      
            tmpOff = np.where(stimInd==j, off, np.nan)      
            onEsts = np.nanmean(tmpEsts*tmpOn, axis=1)
            offEsts = np.nanmean(tmpEsts*tmpOff, axis=1)
            tmp = (onEsts / offEsts) - 1 #np.clip((onEsts / offEsts) - 1, 0, 10000) #TODO: modify?
            tmp = np.where(np.isnan(tmp), 0, tmp)
            # if np.any(np.isnan(tmp)):
            #     print('tmp has nan?')
            #     print('j is ', j)
            #     print('stimInd ', stimInd)
            estsAvg.append(tmp)
        self.estsAvg = np.transpose(np.array(estsAvg))        
        #print('time stimAvg ', time.time()-t)     
        self.stimtime.append(time.time()-t)
        return self.estsAvg

    def plotColorFrame(self):
        ''' Computes colored nicer background+components frame
        '''
        t = time.time()
        image = self.image
        color = np.stack([image, image, image, image], axis=-1).astype(np.uint8).copy()
        color[...,3] = 255
        if self.coords is not None:
            for i,c in enumerate(self.coords):
                #c = np.array(c)
                ind = c[~np.isnan(c).any(axis=1)].astype(int)
                cv2.fillConvexPoly(color, ind, self._tuningColor(i, color[ind[:,1], ind[:,0]]))

        # if self.image.shape[0] < self.image.shape[1]:
        #         self.flip = True
        #         raw = raw.T
        # else:
        #     np.swapaxes(color,0,1)
        #TODO: user input for rotating frame? See Visual class
        #print('time plotColorFrame ', time.time()-t)
        self.colortime.append(time.time()-t)
        return color

    def _tuningColor(self, ind, inten):
        if self.estsAvg[ind] is not None:
            try:
                h = np.nanargmax(self.estsAvg[ind])*36/360
                intensity = 1- np.mean(inten[0][0])/255.0
                r, g, b, = colorsys.hls_to_rgb(h, intensity, 0.8)
                r, g, b = [x*255.0 for x in (r, g, b)]
                return (r, g, b)+ (intensity*150,)
            except ValueError:
                return (255,255,255,0)
        else:
            return (255,255,255,0)

    # def _updateCoords(self, A, dims):
    #     '''See if we need to recalculate the coords
    #        Also see if we need to add components
    #     '''
    #     t = time.time()
    #     if self.A is None: #initial calculation
    #         self.A = A
    #         self.dims = dims
    #         self.coords = self.get_contours(self.A, self.dims)

    #     elif np.shape(A)[1] > np.shape(self.A)[1]: #Only recalc if we have new components
    #         logger.info('Analysis: recomputing contours')
    #         self.A = A
    #         self.dims = dims
    #         self.coords = self.get_contours(self.A, self.dims)

    #     self.updateCoordsTime.append(time.time() - t)
    #     #return self.coords  #Not really necessary
    

    # def get_contours(self, A, dims, thr=0.9, thr_method='nrg', swap_dim=False):
    #     ''' Stripped-down version of visualization get_contours function from caiman'''

    #     """Gets contour of spatial components and returns their coordinates

    #     Args:
    #         A:   np.ndarray or sparse matrix
    #                 Matrix of Spatial components (d x K)

    #             dims: tuple of ints
    #                 Spatial dimensions of movie (x, y[, z])

    #             thr: scalar between 0 and 1
    #                 Energy threshold for computing contours (default 0.9)

    #             thr_method: [optional] string
    #                 Method of thresholding:
    #                     'max' sets to zero pixels that have value less than a fraction of the max value
    #                     'nrg' keeps the pixels that contribute up to a specified fraction of the energy

    #     Returns:
    #         Coor: list of coordinates with center of mass and
    #                 contour plot coordinates (per layer) for each component
    #     """

    #     if 'csc_matrix' not in str(type(A)):
    #         A = csc_matrix(A)
    #     d, nr = np.shape(A)
        
    #     d1, d2 = dims
    #     x, y = np.mgrid[0:d1:1, 0:d2:1]

    #     coordinates = []

    #     # get the center of mass of neurons( patches )
    #     cm = self.com(A, *dims)

    #     # for each patches
    #     #TODO: this does NOT need to be recomputed except when update_shapes has changes...
    #     for i in range(nr):
    #         pars = dict()
    #         # we compute the cumulative sum of the energy of the Ath component that has been ordered from least to highest
    #         patch_data = A.data[A.indptr[i]:A.indptr[i + 1]]
    #         indx = np.argsort(patch_data)[::-1]
    #         cumEn = np.cumsum(patch_data[indx]**2)
    #         # we work with normalized values
    #         cumEn /= cumEn[-1]
    #         Bvec = np.ones(d)
    #         # we put it in a similar matrix
    #         Bvec[A.indices[A.indptr[i]:A.indptr[i + 1]][indx]] = cumEn
    #         Bmat = np.reshape(Bvec, dims, order='F')
    #         pars['coordinates'] = []
    #         # for each dimensions we draw the contour
    #         for B in (Bmat if len(dims) == 3 else [Bmat]):
    #             vertices = find_contours(B.T, thr)
    #             # this fix is necessary for having disjoint figures and borders plotted correctly
    #             v = np.atleast_2d([np.nan, np.nan])
    #             for _, vtx in enumerate(vertices):
    #                 num_close_coords = np.sum(np.isclose(vtx[0, :], vtx[-1, :]))
    #                 if num_close_coords < 2:
    #                     if num_close_coords == 0:
    #                         # case angle
    #                         newpt = np.round(vtx[-1, :] / [d2, d1]) * [d2, d1]
    #                         vtx = np.concatenate((vtx, newpt[np.newaxis, :]), axis=0)
    #                     else:
    #                         # case one is border
    #                         vtx = np.concatenate((vtx, vtx[0, np.newaxis]), axis=0)
    #                 v = np.concatenate(
    #                     (v, vtx, np.atleast_2d([np.nan, np.nan])), axis=0)

    #             pars['coordinates'] = v if len(
    #                 dims) == 2 else (pars['coordinates'] + [v])
    #         pars['CoM'] = np.squeeze(cm[i, :])
    #         pars['neuron_id'] = i + 1
    #         coordinates.append(pars)
    #     return coordinates

    # def com(self, A, d1, d2):
        
    #     Coor = np.matrix([np.outer(np.ones(d2), np.arange(d1)).ravel(),
    #                         np.outer(np.arange(d2), np.ones(d1)).ravel()], dtype=A.dtype)
    #     cm = (Coor * A / A.sum(axis=0)).T
    #     return np.array(cm)