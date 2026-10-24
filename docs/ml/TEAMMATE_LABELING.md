# Roboflow walkthrough for the teammate labeling 15 Test images

Checked against official Roboflow documentation on 2026-10-24. UI button names
vary between layouts; alternatives below cover the supplied team screenshots.
These images are our final Test labels, so keep annotations independent of model
predictions. No training is required for this task.

1. **Prepare your assigned files.** Unzip the 15-image archive Emir sends you.
   Keep filenames unchanged and upload only those 15 PNGs. Do not mix separate
   assigned archives, since they can overlap.

2. **Create a separate project.** Open https://app.roboflow.com and sign in.
   From your workspace's Projects page, click **Create New Project**. Name it
   `dowser-kern-test-helper` and select **Object Detection**. If an Annotation
   Group field is required, use a new group `dowser-kern-test-helper`, separate
   from training projects. That group is not the class name; the actual class
   is created below. Click the project-creation button. [Project docs](https://docs.roboflow.com/datasets/create-and-upload/create-a-project).

3. **Upload.** In the project, click **Upload Data**, then **Select Files**
   and select the 15 unzipped PNGs, or drag them onto the upload area. Confirm
   the count is 15 and click **Save and Continue**. If a split choice appears,
   put every image in **Test** (100% Test, 0% Train, 0% Valid). At the labeling
   choice, select **Label Manually** (called **Label Myself** in some layouts).
   Open the batch from **Annotate** if needed. Keep auto-labeling disabled.
   [Upload docs](https://docs.roboflow.com/adding-data/object-detection).

4. **Draw boxes.** Open the first image. In the editor's upper-right split
   dropdown, select **TEST** if it currently says TRAIN or VALID. Do this for
   every image that is not already Test. Select the rectangle/bounding-box tool
   on the right toolbar, or press **B**. Zoom in and click-drag a tight box
   around one recognizable hollow oil/gas well symbol. Type `well_symbol` in
   the class popup; choose **Create class** if necessary and save the selection.
   Use this exact class for every box. It is normal not to enter a class while
   creating the project. [Annotation tools](https://docs.roboflow.com/annotate/use-roboflow-annotate).

   Our labeling rules:
   - Annotate every recognizable target across the entire image, not only a few.
   - One box per hollow black/gray oil/gas circle; include its outer outline.
   - Exclude solid black circles/tanks, squares/buildings, digits/letters,
     contour loops and blue water-well marks. Do not label shapes just because
     they look round.
   - Close circles still get separate boxes. Boxes may overlap slightly.
   - Include faded or edge-clipped symbols when their identity is clear, boxing
     only the visible portion inside the image.
   - If unsure whether a shape is a target, send Emir the filename and a screenshot
     and leave that image unresolved until the labeling decision is agreed.

5. **Complete every image.** Scan systematically from top-left to bottom-right
   at a readable zoom. Use the next-image arrow to continue, and return once
   to verify that earlier boxes were retained. For an image with no targets
   after full inspection, click **Mark Null**, the crossed-circle icon, or
   press **N**. Choose the reviewed-empty/null action, not Unannotated.
   An unfinished or uncertain image is not a negative. For this independent
   Test task, leave **Find Objects with AI**, **Auto-Label** and **Label Assist**
   unused. [Null annotation tool](https://docs.roboflow.com/annotate/use-roboflow-annotate).

6. **Add the reviewed images to Dataset.** Return to **Annotate**, open the
   batch and its **Annotated** tab. Once all 15 are complete, click
   **Add 15 Images to Dataset**. If a split dialog appears, select the option
   placing all images in **Testing Set**. Keep existing Test assignments if
   offered. The Dataset count should become 15; the batch's Annotated count
   can become zero because the images moved into Dataset. Check that every
   image is Test. If the workspace requires review, Emir/the reviewer must
   approve them before they can be exported. [Dataset/job controls](https://docs.roboflow.com/annotate/team-collaboration).

7. **Create an unchanged export version.** Open **Versions**, then **Create New
   Version** or **Generate New Version**. Name it `manual_test_helper_v1`.
   Keep all 15 images in Test. In **Preprocessing**, remove every step, including
   **Resize** and **Auto-Orient**, using the X/remove controls. Preserve native
   1024 x 1024 dimensions. Leave **Augmentation** empty, continue and click
   **Create** or **Generate**. Only create the dataset snapshot; leave
   **Train Model** unused. If all-Test cannot be retained, send Emir that screen
   before changing the partition. [Version creation](https://docs.roboflow.com/datasets/versions/dataset-versions/create-a-dataset-version),
   [preprocessing](https://docs.roboflow.com/datasets/versions/dataset-versions/image-preprocessing).

8. **Download and return the annotation ZIP.** Open the new version and click
   **Download Dataset** or **Export**. Select **YOLOv8**, choose **Download zip
   to computer**, then **Continue**. Send that downloaded ZIP back to Emir,
   preserving it as downloaded. It must contain all 15 images and their TXT
   annotations, including reviewed-negative images. Send the ZIP containing
   labels, not the original unannotated image ZIP. If any image remained
   uncertain, mention its filename rather than silently marking it empty.
   [Export documentation](https://docs.roboflow.com/exporting-data).

Finished: 15 images reviewed, only `well_symbol` used, all assigned to Test,
no preprocessing/augmentation/AI suggestions, and a YOLOv8 annotation ZIP sent
to Emir. He will audit and merge it with the other Test annotations by tile ID.
