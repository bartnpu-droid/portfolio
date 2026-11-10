<?php
/**
 * Title: Bestsellers (featured products)
 * Slug: ombra/featured-products
 * Categories: ombra, woo-commerce
 * Keywords: products, bestsellers, featured, grid
 * Viewport width: 1400
 *
 * Shows the products marked as "Featured" in WooCommerce, with Ombra badges and scent notes.
 *
 * @package Ombra
 */

?>
<!-- wp:group {"className":"ombra-section","style":{"spacing":{"padding":{"top":"var:preset|spacing|40","bottom":"var:preset|spacing|60"},"blockGap":"var:preset|spacing|40"}},"layout":{"type":"constrained"}} -->
<div class="wp-block-group ombra-section" style="padding-top:var(--wp--preset--spacing--40);padding-bottom:var(--wp--preset--spacing--60)">
<!-- wp:group {"align":"wide","className":"ombra-section__head","layout":{"type":"flex","flexWrap":"wrap","justifyContent":"space-between","verticalAlignment":"bottom"}} -->
<div class="wp-block-group alignwide ombra-section__head">
<!-- wp:heading {"level":2} -->
<h2 class="wp-block-heading"><?php esc_html_e( 'Bestsellers', 'ombra' ); ?></h2>
<!-- /wp:heading -->

<!-- wp:paragraph {"className":"ombra-link-arrow"} -->
<p class="ombra-link-arrow"><a href="<?php echo esc_url( ombra_shop_url() ); ?>"><?php esc_html_e( 'See all products', 'ombra' ); ?></a></p>
<!-- /wp:paragraph -->
</div>
<!-- /wp:group -->

<!-- wp:woocommerce/product-collection {"queryId":11,"query":{"perPage":4,"pages":1,"offset":0,"postType":"product","order":"asc","orderBy":"menu_order","search":"","exclude":[],"inherit":false,"taxQuery":{},"isProductCollectionBlock":true,"featured":true,"woocommerceOnSale":false,"woocommerceStockStatus":["instock","outofstock","onbackorder"],"woocommerceAttributes":[],"woocommerceHandPickedProducts":[]},"tagName":"div","displayLayout":{"type":"flex","columns":4,"shrinkColumns":true},"dimensions":{"widthType":"fill"},"collection":"woocommerce/product-collection/featured","hideControls":["inherit","featured"],"queryContextIncludes":["collection"],"align":"wide","className":"ombra-products"} -->
<div class="wp-block-woocommerce-product-collection alignwide ombra-products">
<!-- wp:woocommerce/product-template -->
<!-- wp:woocommerce/product-image {"showSaleBadge":false,"imageSizing":"thumbnail","isDescendentOfQueryLoop":true,"aspectRatio":"1","style":{"border":{"radius":"6px"}}} -->
<!-- wp:ombra/product-badge /-->
<!-- /wp:woocommerce/product-image -->

<!-- wp:post-title {"level":3,"isLink":true,"fontSize":"large","__woocommerceNamespace":"woocommerce/product-collection/product-title"} /-->

<!-- wp:ombra/scent-notes {"variant":"line"} /-->

<!-- wp:woocommerce/product-price {"isDescendentOfQueryLoop":true,"fontSize":"small"} /-->
<!-- /wp:woocommerce/product-template -->
</div>
<!-- /wp:woocommerce/product-collection -->
</div>
<!-- /wp:group -->
