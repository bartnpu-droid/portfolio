<?php
/**
 * Title: Shop by category
 * Slug: ombra/categories
 * Categories: ombra, woo-commerce
 * Keywords: categories, collections, tiles
 * Viewport width: 1400
 *
 * @package Ombra
 */

$ombra_tiles = array(
	array( 'candles', __( 'Candles', 'ombra' ), 'cat-candles.jpg', __( 'Jars, tins and a terracotta vessel', 'ombra' ) ),
	array( 'diffusers-sprays', __( 'Diffusers + sprays', 'ombra' ), 'cat-diffusers.jpg', __( 'Scent without a flame', 'ombra' ) ),
	array( 'accessories', __( 'Accessories', 'ombra' ), 'cat-accessories.jpg', __( 'Long matches, the right tool', 'ombra' ) ),
	array( 'gift-sets', __( 'Gift sets', 'ombra' ), 'cat-gifts.jpg', __( 'Boxed and ready to give', 'ombra' ) ),
);
?>
<!-- wp:group {"className":"ombra-section","style":{"spacing":{"padding":{"top":"var:preset|spacing|60","bottom":"var:preset|spacing|50"},"blockGap":"var:preset|spacing|40"}},"layout":{"type":"constrained"}} -->
<div class="wp-block-group ombra-section" style="padding-top:var(--wp--preset--spacing--60);padding-bottom:var(--wp--preset--spacing--50)">
<!-- wp:group {"align":"wide","className":"ombra-section__head","layout":{"type":"flex","flexWrap":"wrap","justifyContent":"space-between","verticalAlignment":"bottom"}} -->
<div class="wp-block-group alignwide ombra-section__head">
<!-- wp:heading {"level":2} -->
<h2 class="wp-block-heading"><?php esc_html_e( 'Shop by mood', 'ombra' ); ?></h2>
<!-- /wp:heading -->

<!-- wp:paragraph {"className":"ombra-link-arrow"} -->
<p class="ombra-link-arrow"><a href="<?php echo esc_url( ombra_shop_url() ); ?>"><?php esc_html_e( 'Shop everything', 'ombra' ); ?></a></p>
<!-- /wp:paragraph -->
</div>
<!-- /wp:group -->

<!-- wp:group {"align":"wide","className":"ombra-tiles","layout":{"type":"grid","columnCount":4,"minimumColumnWidth":"14rem"}} -->
<div class="wp-block-group alignwide ombra-tiles">
<?php foreach ( $ombra_tiles as $ombra_tile ) : ?>
<!-- wp:group {"className":"ombra-tile","style":{"spacing":{"blockGap":"0.6rem"}},"layout":{"type":"flex","orientation":"vertical"}} -->
<div class="wp-block-group ombra-tile">
<!-- wp:image {"aspectRatio":"4/5","scale":"cover","sizeSlug":"full","linkDestination":"custom","className":"ombra-tile__image"} -->
<figure class="wp-block-image size-full ombra-tile__image"><a href="<?php echo esc_url( ombra_category_url( $ombra_tile[0] ) ); ?>"><img src="<?php echo esc_url( ombra_image( $ombra_tile[2] ) ); ?>" alt="<?php echo esc_attr( $ombra_tile[1] ); ?>" style="aspect-ratio:4/5;object-fit:cover"/></a></figure>
<!-- /wp:image -->

<!-- wp:heading {"level":3,"fontSize":"large"} -->
<h3 class="wp-block-heading has-large-font-size"><a href="<?php echo esc_url( ombra_category_url( $ombra_tile[0] ) ); ?>"><?php echo esc_html( $ombra_tile[1] ); ?></a></h3>
<!-- /wp:heading -->

<!-- wp:paragraph {"textColor":"contrast-2","fontSize":"small"} -->
<p class="has-contrast-2-color has-text-color has-small-font-size"><?php echo esc_html( $ombra_tile[3] ); ?></p>
<!-- /wp:paragraph -->
</div>
<!-- /wp:group -->
<?php endforeach; ?>
</div>
<!-- /wp:group -->
</div>
<!-- /wp:group -->
